"""Boucle d'agent : Claude décide quels outils appeler, le code les exécute, puis Claude répond.

Boucle écrite à la main (plutôt que le Tool Runner, en bêta) pour garder la main sur chaque
étape : journal des appels d'outils, contrôle des sources citées, limite du nombre de tours.
"""

import re
from dataclasses import dataclass, field

import anthropic

from ..config import Settings, get_settings
from ..retrieval import Recherche
from .outils import DEFINITIONS, Outils, en_json
from .prompt import consigne_systeme

MAX_TOURS_OUTILS = 6  # au-delà, on arrête la boucle : protège des boucles infinies et des coûts
LIGNE_SOURCES = re.compile(r"^\s*\**Sources?\s*:\**\s*(.+)$", re.IGNORECASE | re.MULTILINE)
BETAS = ["server-side-fallback-2026-07-01"]


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
    sources_inventees: list[str] = field(default_factory=list)  # citées mais jamais consultées
    appels: list[AppelOutil] = field(default_factory=list)
    stop_reason: str | None = None
    usage: dict = field(default_factory=dict)


class Assistant:
    """Une instance par processus (le modèle d'embedding est long à charger)."""

    def __init__(self, settings: Settings | None = None, client: anthropic.Anthropic | None = None):
        self.settings = settings or get_settings()
        self.client = client or anthropic.Anthropic()
        self.recherche = Recherche(self.settings)
        self.outils = Outils(self.recherche, self.settings.date_reference)
        self.systeme = consigne_systeme(self.settings.date_reference)

    def nouvelle_conversation(self) -> "Conversation":
        return Conversation(self)

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

    def __init__(self, assistant: Assistant):
        self.assistant = assistant
        self.messages: list = []

    def envoyer(self, question: str) -> Reponse:
        self.messages.append({"role": "user", "content": question})
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
                resultat, erreur = self.assistant.outils.executer(bloc.name, bloc.input)
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
                texte="Je n'arrive pas à finaliser ma réponse. Je vous propose de contacter un "
                      "conseiller au 04 00 00 00 00 (du lundi au vendredi 9h-19h, samedi 10h-17h).",
                appels=appels, stop_reason="max_tours", usage=usage,
            )

        if message.stop_reason == "refusal":
            texte = ("Je ne peux pas répondre à cette demande. Puis-je vous aider sur une question "
                     "concernant NovaTech, vos commandes ou nos produits ?")
        else:
            texte = "\n".join(b.text for b in message.content if b.type == "text").strip()
        return self._finaliser(texte, appels, message.stop_reason, usage)

    @staticmethod
    def _finaliser(texte: str, appels: list[AppelOutil], stop_reason, usage) -> Reponse:
        consultees = {
            p["source"]
            for a in appels if a.nom == "rechercher_informations" and not a.erreur
            for p in a.resultat["passages"]
        }
        citees = []
        if m := LIGNE_SOURCES.search(texte):
            citees = [s.strip(" .*`[]") for s in m.group(1).split(",") if s.strip(" .*`[]")]
        return Reponse(
            texte=texte,
            sources=[s for s in citees if s in consultees],
            sources_inventees=[s for s in citees if s not in consultees],
            appels=appels,
            stop_reason=stop_reason,
            usage=usage,
        )
