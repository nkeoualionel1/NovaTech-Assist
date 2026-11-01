"""API web de NovaTech Assist.

Lancement : uvicorn novatech.api.app:app --port 8000
Documentation interactive : http://localhost:8000/docs

Une réponse est envoyée en flux (Server-Sent Events) :
    event: outil     {"nom": "verifier_stock", "libelle": "Vérification du stock…"}   (0 à n fois)
    event: reponse   {"texte": "...", "sources": [...], ...}                            (1 fois)
    event: erreur    {"message": "..."}                                                 (en cas d'échec)
Le texte arrive en une fois : les garde-fous de sortie doivent voir la réponse complète
avant qu'elle ne soit affichée.
"""

import json
import queue
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import anthropic
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .. import garde_fous as gf
from ..assistant import Assistant, Conversation, Reponse
from ..garde_fous.filtres import LIGNE_SOURCES
from ..garde_fous.limites import Limiteur

LIBELLES_OUTILS = {
    "rechercher_informations": "Recherche dans la documentation…",
    "verifier_stock": "Vérification du stock…",
    "suivi_commande": "Consultation de votre commande…",
    "transferer_conseiller": "Transmission à un conseiller…",
}
DUREE_VIE_CONVERSATION_S = 3600
MAX_CONVERSATIONS = 1000
MESSAGES_PAR_MINUTE_PAR_IP = 10
DOSSIER_FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "dist"


class Etat:
    """Ressources partagées, créées une seule fois au démarrage."""

    assistant: Assistant
    conversations: dict[str, tuple[Conversation, float]] = {}
    verrou = threading.Lock()
    limite_messages = Limiteur(MESSAGES_PAR_MINUTE_PAR_IP, 60)


@asynccontextmanager
async def cycle_de_vie(app: FastAPI):
    Etat.assistant = Assistant()
    Etat.assistant.recherche.embedder.model  # charge le modèle maintenant, pas à la 1re question
    yield
    Etat.assistant.recherche.fermer()


app = FastAPI(title="NovaTech Assist", version="0.7.0", lifespan=cycle_de_vie)


# --- Modèles de requête / réponse -----------------------------------------------------

class NouvelleConversation(BaseModel):
    id: str


class Message(BaseModel):
    # Limite large ici (protège le serveur) ; l'agent répond poliment au-delà de 2 000 caractères.
    question: str = Field(min_length=1, max_length=10 * gf.LONGUEUR_MAX_MESSAGE)


# --- Conversations ---------------------------------------------------------------------

def _ip(request: Request) -> str:
    return request.client.host if request.client else "inconnue"


def _purger_conversations() -> None:
    limite = time.monotonic() - DUREE_VIE_CONVERSATION_S
    for cle in [c for c, (_, vu) in Etat.conversations.items() if vu < limite]:
        del Etat.conversations[cle]


@app.post("/api/conversations", response_model=NouvelleConversation)
def creer_conversation(request: Request) -> NouvelleConversation:
    with Etat.verrou:
        _purger_conversations()
        if len(Etat.conversations) >= MAX_CONVERSATIONS:
            raise HTTPException(503, "Service saturé, réessayez dans quelques minutes.")
        conversation = Etat.assistant.nouvelle_conversation(cle_client=_ip(request))
        Etat.conversations[conversation.id] = (conversation, time.monotonic())
    return NouvelleConversation(id=conversation.id)


@app.post("/api/conversations/{conversation_id}/messages")
def envoyer_message(conversation_id: str, message: Message, request: Request) -> StreamingResponse:
    with Etat.verrou:
        entree = Etat.conversations.get(conversation_id)
        if entree is None:
            raise HTTPException(404, "Conversation inconnue ou expirée.")
        conversation = entree[0]
        Etat.conversations[conversation_id] = (conversation, time.monotonic())
    if not Etat.limite_messages.consommer(_ip(request)):
        raise HTTPException(429, "Trop de messages envoyés. Patientez une minute.")

    return StreamingResponse(
        _flux_reponse(conversation, message.question),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _flux_reponse(conversation: Conversation, question: str):
    """L'agent tourne dans un thread ; ses événements sont relayés au navigateur au fil de l'eau."""
    file: queue.Queue = queue.Queue()

    def travailler():
        try:
            reponse = conversation.envoyer(question, on_evenement=file.put)
            file.put({"type": "reponse", **_serialiser(reponse)})
        except anthropic.APIStatusError as exc:
            file.put({"type": "erreur", "message": _message_erreur_api(exc.status_code)})
        except anthropic.APIConnectionError:
            file.put({"type": "erreur", "message": "Service momentanément indisponible. Réessayez."})
        except Exception:
            file.put({"type": "erreur", "message": "Une erreur inattendue est survenue."})
            raise

    threading.Thread(target=travailler, daemon=True).start()
    while True:
        evenement = file.get()
        type_ = evenement.pop("type")
        if type_ == "outil":
            evenement["libelle"] = LIBELLES_OUTILS.get(evenement["nom"], "Recherche…")
        yield f"event: {type_}\ndata: {json.dumps(evenement, ensure_ascii=False)}\n\n"
        if type_ in ("reponse", "erreur"):
            break


def _message_erreur_api(statut: int) -> str:
    if statut == 429:
        return "L'assistant est très sollicité. Réessayez dans un instant."
    if statut >= 500:
        return "Le service est momentanément indisponible. Réessayez dans un instant."
    return "Votre demande n'a pas pu être traitée."


def _serialiser(reponse: Reponse) -> dict:
    """Prépare la réponse pour l'affichage : la ligne « Sources » devient des liens."""
    passages = {}
    for appel in reponse.appels:
        if appel.nom == "rechercher_informations" and not appel.erreur:
            for p in appel.resultat["passages"]:
                passages.setdefault(p["source"], p)
    sources = [
        {"id": s, "titre": passages[s]["titre"],
         "type": "produit" if s.startswith("NT-") else "document"}
        for s in reponse.sources if s in passages
    ]
    texte = LIGNE_SOURCES.sub("", reponse.texte).rstrip()
    return {
        "texte": texte,
        "sources": sources,
        "outils": [a.nom for a in reponse.appels],
        "transfert": next((a.resultat for a in reponse.appels
                           if a.nom == "transferer_conseiller" and not a.erreur), None),
    }


# --- Sources ---------------------------------------------------------------------------------

@app.get("/api/sources/{source_id}")
def lire_source(source_id: str) -> dict:
    """Contenu d'un document ou d'une fiche produit cité, pour l'afficher au client."""
    lignes = Etat.assistant.recherche.conn.execute(
        "SELECT titre, section, contenu, source_type FROM chunks WHERE source_id = %s ORDER BY id",
        [source_id],
    ).fetchall()
    if not lignes:
        raise HTTPException(404, "Source inconnue.")
    morceaux = [f"## {section}\n\n{contenu}" if section else contenu
                for _, section, contenu, _ in lignes]
    return {"id": source_id, "titre": lignes[0][0], "type": lignes[0][3],
            "contenu": "\n\n".join(morceaux)}


@app.get("/api/sante")
def sante() -> dict:
    Etat.assistant.recherche.conn.execute("SELECT 1")
    return {"statut": "ok", "modele": Etat.assistant.settings.claude_model}


# --- Interface (version construite par « npm run build ») ---------------------------------

if DOSSIER_FRONTEND.exists():
    app.mount("/assets", StaticFiles(directory=DOSSIER_FRONTEND / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def accueil() -> FileResponse:
        return FileResponse(DOSSIER_FRONTEND / "index.html")
