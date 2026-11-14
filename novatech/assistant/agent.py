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

from .. import guardrails
from ..config import Settings, get_settings
from ..guardrails.audit_log import AuditLog
from ..guardrails.rate_limit import RateLimiter
from ..retrieval import Retriever
from .prompt import build_system_prompt
from .tools import TOOL_DEFINITIONS, Toolbox, to_json

MAX_TOOL_ROUNDS = 6  # au-delà, on arrête la boucle : protège des boucles infinies et des coûts
BETAS = ["server-side-fallback-2026-07-01"]
ORDER_NUMBER_RE = re.compile(r"CMD-\d{5}", re.IGNORECASE)
CONTACT = "04 00 00 00 00 (du lundi au vendredi de 9h à 19h, le samedi de 10h à 17h)"


@dataclass
class ToolCall:
    name: str
    input: dict
    result: dict
    is_error: bool


@dataclass
class Reply:
    text: str
    sources: list[str] = field(default_factory=list)  # sources citées ET réellement consultées
    tool_calls: list[ToolCall] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)  # déclenchements des garde-fous
    stop_reason: str | None = None
    usage: dict = field(default_factory=dict)
    model: str | None = None  # modèle qui a réellement répondu (peut différer en cas de repli)


class Assistant:
    """Une instance par processus (le modèle d'embedding est long à charger)."""

    def __init__(self, settings: Settings | None = None, client: anthropic.Anthropic | None = None,
                 enable_audit_log: bool = True):
        self.settings = settings or get_settings()
        self.client = client or anthropic.Anthropic()
        self.retriever = Retriever(self.settings)
        self.toolbox = Toolbox(self.retriever, self.settings.reference_date)
        self.system_prompt = build_system_prompt(self.settings.reference_date)
        self.audit_log = AuditLog(self.retriever.conn) if enable_audit_log else None
        self.order_lookup_failures = RateLimiter(guardrails.MAX_ORDER_LOOKUP_FAILURES,
                                                 guardrails.ORDER_LOOKUP_WINDOW_S)

    def new_conversation(self, client_key: str | None = None) -> "Conversation":
        """client_key : identifie le client entre conversations (adresse IP côté API)."""
        return Conversation(self, client_key)

    def _call_claude(self, messages: list) -> anthropic.types.beta.BetaMessage:
        return self.client.beta.messages.create(
            model=self.settings.claude_model,
            max_tokens=16000,
            system=self.system_prompt,
            tools=TOOL_DEFINITIONS,
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

    def __init__(self, assistant: Assistant, client_key: str | None = None):
        self.assistant = assistant
        self.id = uuid.uuid4().hex
        self.client_key = client_key or self.id
        self.messages: list = []
        self.customer_texts: list[str] = []  # messages du client, après masquage
        self.failed_order_lookups = 0
        self._notify: Callable[[dict], None] = lambda event: None

    def send(self, question: str, on_event: Callable[[dict], None] | None = None) -> Reply:
        """on_event est appelé à chaque appel d'outil (pour afficher la progression)."""
        self._notify = on_event or (lambda event: None)
        start = time.perf_counter()
        reply, masked_question = self._process(question)
        if self.assistant.audit_log:
            duration_ms = int((time.perf_counter() - start) * 1000)
            self.assistant.audit_log.record(self.id, masked_question, reply, duration_ms)
        return reply

    def _process(self, question: str) -> tuple[Reply, str]:
        # --- Avant le modèle -------------------------------------------------------------
        if len(question) > guardrails.MAX_MESSAGE_LENGTH:
            return Reply(
                text=f"Votre message est trop long (plus de {guardrails.MAX_MESSAGE_LENGTH} "
                     "caractères). Pouvez-vous le résumer en quelques phrases ?",
                alerts=["message_too_long"], stop_reason="guardrail",
            ), question[:200] + "…"
        if len(self.customer_texts) >= guardrails.MAX_MESSAGES_PER_CONVERSATION:
            return Reply(
                text="Cette conversation a atteint sa longueur maximale. Pour continuer, ouvrez une "
                     f"nouvelle conversation ou contactez un conseiller au {CONTACT}.",
                alerts=["conversation_too_long"], stop_reason="guardrail",
            ), question

        # Les données sensibles sont masquées AVANT d'être envoyées à l'API ou enregistrées.
        question, alerts = guardrails.mask_sensitive_data(question)
        if guardrails.detect_injection(question):
            alerts.append("injection_suspected")
        self.customer_texts.append(question)
        self.messages.append({"role": "user", "content": question})

        # --- Boucle modèle / outils ----------------------------------------------------------
        tool_calls: list[ToolCall] = []
        usage = {"input_tokens": 0, "output_tokens": 0,
                 "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}

        for _ in range(MAX_TOOL_ROUNDS + 1):
            message = self.assistant._call_claude(self.messages)
            for key in usage:
                usage[key] += getattr(message.usage, key, 0) or 0
            # On renvoie le contenu complet (blocs de réflexion compris), sans le modifier.
            self.messages.append({"role": "assistant", "content": message.content})

            if message.stop_reason == "pause_turn":
                continue
            if message.stop_reason != "tool_use":
                break

            tool_results = []
            for block in message.content:
                if block.type != "tool_use":
                    continue
                result, is_error = self._execute_tool(block.name, block.input, alerts)
                tool_calls.append(ToolCall(block.name, block.input, result, is_error))
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": to_json(result),
                    "is_error": is_error,
                })
            # Tous les résultats dans UN seul message, pour permettre les appels en parallèle.
            self.messages.append({"role": "user", "content": tool_results})
        else:
            return Reply(
                text=f"Je n'arrive pas à finaliser ma réponse. Je vous propose de contacter un "
                     f"conseiller au {CONTACT}.",
                tool_calls=tool_calls, alerts=alerts + ["max_tool_rounds"],
                stop_reason="max_tool_rounds", usage=usage,
            ), question

        # --- Après le modèle -----------------------------------------------------------------
        if message.stop_reason == "refusal":
            text = ("Je ne peux pas répondre à cette demande. Puis-je vous aider sur une question "
                    "concernant NovaTech, vos commandes ou nos produits ?")
        else:
            text = "\n".join(b.text for b in message.content if b.type == "text").strip()

        read_sources = {
            passage["source"]
            for call in tool_calls if call.name == "search_knowledge_base" and not call.is_error
            for passage in call.result["passages"]
        }
        text, output_alerts = guardrails.sanitize_reply(
            text, self.customer_texts, self.assistant.system_prompt, read_sources
        )
        return Reply(
            text=text,
            sources=guardrails.cited_sources(text),
            tool_calls=tool_calls,
            alerts=alerts + output_alerts,
            stop_reason=message.stop_reason,
            usage=usage,
            model=getattr(message, "model", None),
        ), question

    def _execute_tool(self, name: str, tool_input: dict, alerts: list[str]) -> tuple[dict, bool]:
        """Contrôles propres à la conversation, puis exécution de l'outil."""
        self._notify({"type": "tool", "name": name})
        if name == "track_order":
            refusal = self._check_order_lookup(tool_input)
            if refusal:
                alerts.append(refusal[0])
                return {"error": refusal[1]}, True

        result, is_error = self.assistant.toolbox.execute(name, tool_input)
        if name == "track_order" and is_error:
            self.failed_order_lookups += 1
            self.assistant.order_lookup_failures.record(self.client_key)
        return result, is_error

    def _check_order_lookup(self, tool_input: dict) -> tuple[str, str] | None:
        if self.assistant.order_lookup_failures.is_exceeded(self.client_key):
            return ("order_lookup_blocked",
                    "Trop de tentatives infructueuses dans cette conversation : n'essayez plus. "
                    "Proposez au client de contacter un conseiller.")
        # Le numéro et l'e-mail doivent venir du CLIENT, pas d'un document ni d'une supposition.
        given_numbers = {n.upper() for t in self.customer_texts for n in ORDER_NUMBER_RE.findall(t)}
        if str(tool_input.get("order_number", "")).strip().upper() not in given_numbers:
            return ("order_number_not_given_by_customer",
                    "Ce numéro de commande n'a pas été donné par le client : demandez-le-lui.")
        if str(tool_input.get("email", "")).strip().lower() not in guardrails.allowed_emails(self.customer_texts):
            return ("email_not_given_by_customer",
                    "Cette adresse e-mail n'a pas été donnée par le client : demandez-lui l'e-mail "
                    "utilisé lors de la commande.")
        return None
