"""API web de NovaTech Assist.

Lancement : uvicorn novatech.api.app:app --port 8000
Documentation interactive : http://localhost:8000/docs

Une réponse est envoyée en flux (Server-Sent Events) :
    event: tool    {"name": "check_stock", "label": "Vérification du stock…"}   (0 à n fois)
    event: reply   {"text": "...", "sources": [...], ...}                          (1 fois)
    event: error   {"message": "..."}                                              (en cas d'échec)
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

from .. import guardrails
from ..assistant import Assistant, Conversation, Reply
from ..guardrails.filters import SOURCES_LINE_RE
from ..guardrails.rate_limit import RateLimiter

# Libellés affichés dans l'interface pendant que Claude utilise un outil.
TOOL_LABELS = {
    "search_knowledge_base": "Recherche dans la documentation…",
    "check_stock": "Vérification du stock…",
    "track_order": "Consultation de votre commande…",
    "transfer_to_agent": "Transmission à un conseiller…",
}
CONVERSATION_TTL_S = 3600
MAX_CONVERSATIONS = 1000
MESSAGES_PER_MINUTE_PER_IP = 10
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"


class AppState:
    """Ressources partagées, créées une seule fois au démarrage."""

    assistant: Assistant
    conversations: dict[str, tuple[Conversation, float]] = {}
    lock = threading.Lock()
    message_limiter = RateLimiter(MESSAGES_PER_MINUTE_PER_IP, 60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    AppState.assistant = Assistant()
    AppState.assistant.retriever.embedder.model  # charge le modèle maintenant, pas à la 1re question
    yield
    AppState.assistant.retriever.close()


app = FastAPI(title="NovaTech Assist", version="0.8.0", lifespan=lifespan)


# --- Modèles de requête / réponse -----------------------------------------------------

class ConversationCreated(BaseModel):
    id: str


class MessageIn(BaseModel):
    # Limite large ici (protège le serveur) ; l'agent répond poliment au-delà de 2 000 caractères.
    question: str = Field(min_length=1, max_length=10 * guardrails.MAX_MESSAGE_LENGTH)


# --- Conversations ---------------------------------------------------------------------

def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _prune_conversations() -> None:
    cutoff = time.monotonic() - CONVERSATION_TTL_S
    for key in [k for k, (_, last_seen) in AppState.conversations.items() if last_seen < cutoff]:
        del AppState.conversations[key]


@app.post("/api/conversations", response_model=ConversationCreated)
def create_conversation(request: Request) -> ConversationCreated:
    with AppState.lock:
        _prune_conversations()
        if len(AppState.conversations) >= MAX_CONVERSATIONS:
            raise HTTPException(503, "Service saturé, réessayez dans quelques minutes.")
        conversation = AppState.assistant.new_conversation(client_key=_client_ip(request))
        AppState.conversations[conversation.id] = (conversation, time.monotonic())
    return ConversationCreated(id=conversation.id)


@app.post("/api/conversations/{conversation_id}/messages")
def post_message(conversation_id: str, message: MessageIn, request: Request) -> StreamingResponse:
    with AppState.lock:
        entry = AppState.conversations.get(conversation_id)
        if entry is None:
            raise HTTPException(404, "Conversation inconnue ou expirée.")
        conversation = entry[0]
        AppState.conversations[conversation_id] = (conversation, time.monotonic())
    if not AppState.message_limiter.try_acquire(_client_ip(request)):
        raise HTTPException(429, "Trop de messages envoyés. Patientez une minute.")

    return StreamingResponse(
        _stream_reply(conversation, message.question),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _stream_reply(conversation: Conversation, question: str):
    """L'agent tourne dans un thread ; ses événements sont relayés au navigateur au fil de l'eau."""
    events: queue.Queue = queue.Queue()

    def worker():
        try:
            reply = conversation.send(question, on_event=events.put)
            events.put({"type": "reply", **_serialize_reply(reply)})
        except anthropic.APIStatusError as exc:
            events.put({"type": "error", "message": _api_error_message(exc.status_code)})
        except anthropic.APIConnectionError:
            events.put({"type": "error", "message": "Service momentanément indisponible. Réessayez."})
        except Exception:
            events.put({"type": "error", "message": "Une erreur inattendue est survenue."})
            raise

    threading.Thread(target=worker, daemon=True).start()
    while True:
        event = events.get()
        event_type = event.pop("type")
        if event_type == "tool":
            event["label"] = TOOL_LABELS.get(event["name"], "Recherche…")
        yield f"event: {event_type}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
        if event_type in ("reply", "error"):
            break


def _api_error_message(status_code: int) -> str:
    if status_code == 429:
        return "L'assistant est très sollicité. Réessayez dans un instant."
    if status_code >= 500:
        return "Le service est momentanément indisponible. Réessayez dans un instant."
    return "Votre demande n'a pas pu être traitée."


def _serialize_reply(reply: Reply) -> dict:
    """Prépare la réponse pour l'affichage : la ligne « Sources » devient des liens."""
    passages = {}
    for call in reply.tool_calls:
        if call.name == "search_knowledge_base" and not call.is_error:
            for passage in call.result["passages"]:
                passages.setdefault(passage["source"], passage)
    sources = [
        {"id": s, "title": passages[s]["title"],
         "type": "product" if s.startswith("NT-") else "document"}
        for s in reply.sources if s in passages
    ]
    text = SOURCES_LINE_RE.sub("", reply.text).rstrip()
    return {
        "text": text,
        "sources": sources,
        "tools": [call.name for call in reply.tool_calls],
        "handoff": next((call.result for call in reply.tool_calls
                         if call.name == "transfer_to_agent" and not call.is_error), None),
    }


# --- Sources ---------------------------------------------------------------------------------

@app.get("/api/sources/{source_id}")
def get_source(source_id: str) -> dict:
    """Contenu d'un document ou d'une fiche produit cité, pour l'afficher au client."""
    rows = AppState.assistant.retriever.conn.execute(
        "SELECT title, section, content, source_type FROM chunks WHERE source_id = %s ORDER BY id",
        [source_id],
    ).fetchall()
    if not rows:
        raise HTTPException(404, "Source inconnue.")
    pieces = [f"## {section}\n\n{content}" if section else content
              for _, section, content, _ in rows]
    return {"id": source_id, "title": rows[0][0], "type": rows[0][3], "content": "\n\n".join(pieces)}


@app.get("/api/health")
def health() -> dict:
    AppState.assistant.retriever.conn.execute("SELECT 1")
    return {"status": "ok", "model": AppState.assistant.settings.claude_model}


# --- Interface (version construite par « npm run build ») ---------------------------------

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")
