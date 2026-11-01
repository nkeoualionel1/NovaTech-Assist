"""Tests de l'API web avec un faux Claude (aucun appel payant)."""

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from novatech.api import app as module_api
from novatech.assistant.agent import Assistant
from novatech.garde_fous.limites import Limiteur
from test_assistant import FauxClaude, _message
from test_retrieval import base

pytestmark = base


@pytest.fixture
def client():
    def preparer(reponses):
        assistant = Assistant(client=FauxClaude(reponses), journaliser=False)
        module_api.Etat.assistant = assistant
        module_api.Etat.conversations.clear()
        module_api.Etat.limite_messages = Limiteur(module_api.MESSAGES_PAR_MINUTE_PAR_IP, 60)
        preparer.assistants.append(assistant)
        # Sans « with », TestClient ne lance pas le cycle de vie (qui créerait un vrai client Claude).
        return TestClient(module_api.app)

    preparer.assistants = []
    yield preparer
    for a in preparer.assistants:
        a.recherche.fermer()


def _evenements(texte_flux: str) -> list[tuple[str, dict]]:
    evenements = []
    for bloc in texte_flux.strip().split("\n\n"):
        lignes = dict(l.split(": ", 1) for l in bloc.splitlines())
        evenements.append((lignes["event"], json.loads(lignes["data"])))
    return evenements


def test_flux_etapes_puis_reponse_avec_sources(client):
    http = client([
        _message("tool_use", SimpleNamespace(type="tool_use", id="t1", name="rechercher_informations",
                                             input={"requete": "livraison Suisse"})),
        _message("end_turn", SimpleNamespace(
            type="text", text="Non, nous ne livrons pas en Suisse.\n\nSources : livraison")),
    ])
    conversation = http.post("/api/conversations").json()["id"]
    flux = http.post(f"/api/conversations/{conversation}/messages",
                     json={"question": "Livrez-vous en Suisse ?"})
    assert flux.headers["content-type"].startswith("text/event-stream")

    evenements = _evenements(flux.text)
    assert evenements[0] == ("outil", {"nom": "rechercher_informations",
                                       "libelle": "Recherche dans la documentation…"})
    type_, reponse = evenements[-1]
    assert type_ == "reponse"
    assert reponse["texte"] == "Non, nous ne livrons pas en Suisse."  # ligne « Sources » retirée
    assert reponse["sources"][0]["id"] == "livraison" and reponse["sources"][0]["type"] == "document"


def test_conversation_inconnue(client):
    http = client([])
    assert http.post("/api/conversations/inconnue/messages", json={"question": "?"}).status_code == 404


def test_limite_de_messages_par_ip(client):
    texte = SimpleNamespace(type="text", text="Bonjour !")
    http = client([_message("end_turn", texte) for _ in range(20)])
    conversation = http.post("/api/conversations").json()["id"]
    statuts = [http.post(f"/api/conversations/{conversation}/messages",
                         json={"question": "Bonjour"}).status_code for _ in range(11)]
    assert statuts[:10] == [200] * 10 and statuts[10] == 429


def test_lecture_d_une_source(client):
    http = client([])
    source = http.get("/api/sources/livraison").json()
    assert source["titre"].startswith("Livraison") and "Belgique" in source["contenu"]
    assert http.get("/api/sources/inexistante").status_code == 404
