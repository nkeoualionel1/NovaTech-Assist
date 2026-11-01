"""Boucle d'agent : Claude décide quels outils appeler, le code les exécute, puis Claude répond.

Boucle écrite à la main (plutôt que le Tool Runner, en bêta) pour garder la main sur chaque
étape : garde-fous avant/pendant/après l'appel au modèle, journal, limite du nombre de tours.
"""

import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

import anthropic

from .. import garde_fous as gf
from ..config import Settings, get_settings
from ..garde_fous.journal import Journal
from ..garde_fous.limites import Limiteur
from ..retrieval import Recherche
from .outils import DEFINITIONS, Outils, en_json
from .prompt import consigne_systeme

MAX_TOURS_OUTILS = 6  # au-delà, on arrête la boucle : protège des boucles infinies et des coûts
BETAS = ["server-side-fallback-2026-07-01"]
NUMERO_COMMANDE = re.compile(r"CMD-\d{5}", re.IGNORECASE)
CONTACT = "04 00 00 00 00 (du lundi au vendredi de 9h à 19h, le samedi de 10h à 17h)"


@dataclass
class AppelOutil:
    nom: str
    entree: dict
    resultat: dict
    erreur: bool


@dataclass
class Reponse:
    texte: str
    sources: list[str] = field(default_factory=list)  # sources citées ET réellement consultées
    appels: list[AppelOutil] = field(default_factory=list)
    alertes: list[str] = field(default_factory=list)  # déclenchements des garde-fous
    stop_reason: str | None = None
    usage: dict = field(default_factory=dict)
    modele: str | None = None  # modèle qui a réellement répondu (peut différer en cas de repli)


class Assistant:
    """Une instance par processus (le modèle d'embedding est long à charger)."""

    def __init__(self, settings: Settings | None = None, client: anthropic.Anthropic | None = None,
                 journaliser: bool = True):
        self.settings = settings or get_settings()
        self.client = client or anthropic.Anthropic()
        self.recherche = Recherche(self.settings)
        self.outils = Outils(self.recherche, self.settings.date_reference)
        self.systeme = consigne_systeme(self.settings.date_reference)
        self.journal = Journal(self.recherche.conn) if journaliser else None
        self.echecs_suivi = Limiteur(gf.ECHECS_MAX_SUIVI_COMMANDE, gf.FENETRE_ECHECS_SUIVI_S)

    def nouvelle_conversation(self, cle_client: str | None = None) -> "Conversation":
        """cle_client : identifie le client entre conversations (adresse IP côté API)."""
        return Conversation(self, cle_client)

    def _appeler_claude(self, messages: list) -> anthropic.types.beta.BetaMessage:
        return self.client.beta.messages.create(
            model=self.settings.claude_model,
            max_tokens=16000,
            system=self.systeme,
            tools=DEFINITIONS,
            messages=messages,
            output_config={"effort": self.settings.claude_effort},
            # Consigne + outils identiques à chaque appel : mis en cache, ~10x moins chers.
            cache_control={"type": "ephemeral"},
            # Si un filtre de sécurité refuse la requête, l'API la rejoue sur un autre modèle.
            betas=BETAS,
            fallbacks="default",
        )


class Conversation:
    """Historique d'un échange avec un client. Il n'est jamais modifié, seulement complété."""

    def __init__(self, assistant: Assistant, cle_client: str | None = None):
        self.assistant = assistant
        self.id = uuid.uuid4().hex
        self.cle_client = cle_client or self.id
        self.messages: list = []
        self.textes_client: list[str] = []  # messages du client, après masquage
        self.echecs_suivi_commande = 0
        self._notifier: Callable[[dict], None] = lambda evenement: None

    def envoyer(self, question: str,
                on_evenement: Callable[[dict], None] | None = None) -> Reponse:
        """on_evenement est appelé à chaque appel d'outil (pour afficher la progression)."""
        self._notifier = on_evenement or (lambda evenement: None)
        debut = time.perf_counter()
        reponse, question_masquee = self._traiter(question)
        if self.assistant.journal:
            duree = int((time.perf_counter() - debut) * 1000)
            self.assistant.journal.enregistrer(self.id, question_masquee, reponse, duree)
        return reponse

    def _traiter(self, question: str) -> tuple[Reponse, str]:
        # --- Avant le modèle -------------------------------------------------------------
        if len(question) > gf.LONGUEUR_MAX_MESSAGE:
            return Reponse(
                texte=f"Votre message est trop long (plus de {gf.LONGUEUR_MAX_MESSAGE} caractères). "
                      "Pouvez-vous le résumer en quelques phrases ?",
                alertes=["message_trop_long"], stop_reason="garde_fou",
            ), question[:200] + "…"
        if len(self.textes_client) >= gf.MESSAGES_MAX_PAR_CONVERSATION:
            return Reponse(
                texte="Cette conversation a atteint sa longueur maximale. Pour continuer, ouvrez une "
                      f"nouvelle conversation ou contactez un conseiller au {CONTACT}.",
                alertes=["conversation_trop_longue"], stop_reason="garde_fou",
            ), question

        # Les données sensibles sont masquées AVANT d'être envoyées à l'API ou enregistrées.
        question, alertes = gf.masquer_donnees_sensibles(question)
        if gf.detecter_injection(question):
            alertes.append("injection_suspectee")
        self.textes_client.append(question)
        self.messages.append({"role": "user", "content": question})

        # --- Boucle modèle / outils ----------------------------------------------------------
        appels: list[AppelOutil] = []
        usage = {"input_tokens": 0, "output_tokens": 0,
                 "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}

        for _ in range(MAX_TOURS_OUTILS + 1):
            message = self.assistant._appeler_claude(self.messages)
            for cle in usage:
                usage[cle] += getattr(message.usage, cle, 0) or 0
            # On renvoie le contenu complet (blocs de réflexion compris), sans le modifier.
            self.messages.append({"role": "assistant", "content": message.content})

            if message.stop_reason == "pause_turn":
                continue
            if message.stop_reason != "tool_use":
                break

            resultats = []
            for bloc in message.content:
                if bloc.type != "tool_use":
                    continue
                resultat, erreur = self._executer_outil(bloc.name, bloc.input, alertes)
                appels.append(AppelOutil(bloc.name, bloc.input, resultat, erreur))
                resultats.append({
                    "type": "tool_result",
                    "tool_use_id": bloc.id,
                    "content": en_json(resultat),
                    "is_error": erreur,
                })
            # Tous les résultats dans UN seul message, pour permettre les appels en parallèle.
            self.messages.append({"role": "user", "content": resultats})
        else:
            return Reponse(
                texte=f"Je n'arrive pas à finaliser ma réponse. Je vous propose de contacter un "
                      f"conseiller au {CONTACT}.",
                appels=appels, alertes=alertes + ["max_tours"], stop_reason="max_tours", usage=usage,
            ), question

        # --- Après le modèle -----------------------------------------------------------------
        if message.stop_reason == "refusal":
            texte = ("Je ne peux pas répondre à cette demande. Puis-je vous aider sur une question "
                     "concernant NovaTech, vos commandes ou nos produits ?")
        else:
            texte = "\n".join(b.text for b in message.content if b.type == "text").strip()

        consultees = {
            p["source"]
            for a in appels if a.nom == "rechercher_informations" and not a.erreur
            for p in a.resultat["passages"]
        }
        texte, alertes_sortie = gf.nettoyer_reponse(
            texte, self.textes_client, self.assistant.systeme, consultees
        )
        return Reponse(
            texte=texte,
            sources=gf.sources_citees(texte),
            appels=appels,
            alertes=alertes + alertes_sortie,
            stop_reason=message.stop_reason,
            usage=usage,
            modele=getattr(message, "model", None),
        ), question

    def _executer_outil(self, nom: str, entree: dict, alertes: list[str]) -> tuple[dict, bool]:
        """Contrôles propres à la conversation, puis exécution de l'outil."""
        self._notifier({"type": "outil", "nom": nom})
        if nom == "suivi_commande":
            refus = self._controler_suivi_commande(entree)
            if refus:
                alertes.append(refus[0])
                return {"erreur": refus[1]}, True

        resultat, erreur = self.assistant.outils.executer(nom, entree)
        if nom == "suivi_commande" and erreur:
            self.echecs_suivi_commande += 1
            self.assistant.echecs_suivi.enregistrer(self.cle_client)
        return resultat, erreur

    def _controler_suivi_commande(self, entree: dict) -> tuple[str, str] | None:
        if self.assistant.echecs_suivi.depasse(self.cle_client):
            return ("suivi_commande_bloque",
                    "Trop de tentatives infructueuses dans cette conversation : n'essayez plus. "
                    "Proposez au client de contacter un conseiller.")
        # Le numéro et l'e-mail doivent venir du CLIENT, pas d'un document ni d'une supposition.
        numeros = {n.upper() for t in self.textes_client for n in NUMERO_COMMANDE.findall(t)}
        if str(entree.get("numero_commande", "")).strip().upper() not in numeros:
            return ("numero_non_fourni_par_le_client",
                    "Ce numéro de commande n'a pas été donné par le client : demandez-le-lui.")
        if str(entree.get("email", "")).strip().lower() not in gf.emails_autorises(self.textes_client):
            return ("email_non_fourni_par_le_client",
                    "Cette adresse e-mail n'a pas été donnée par le client : demandez-lui l'e-mail "
                    "utilisé lors de la commande.")
        return None
