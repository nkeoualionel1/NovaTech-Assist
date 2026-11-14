"""Tests de l'API web avec un faux Claude (aucun appel payant)."""

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from novatech.api import app as api_module
from novatech.assistant.agent import Assistant
from novatech.guardrails.rate_limit import RateLimiter
from test_assistant import FakeClaude, make_message
from test_retrieval import requires_db

pytestmark = requires_db


@pytest.fixture
def make_client():
    assistants = []

    def factory(replies):
        assistant = Assistant(client=FakeClaude(replies), enable_audit_log=False)
        api_module.AppState.assistant = assistant
        api_module.AppState.conversations.clear()
        api_module.AppState.message_limiter = RateLimiter(api_module.MESSAGES_PER_MINUTE_PER_IP, 60)
        assistants.append(assistant)
        # Sans « with », TestClient ne lance pas le cycle de vie (qui créerait un vrai client Claude).
        return TestClient(api_module.app)

    yield factory
    for assistant in assistants:
        assistant.retriever.close()


def _parse_events(stream_text: str) -> list[tuple[str, dict]]:
    events = []
    for block in stream_text.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((fields["event"], json.loads(fields["data"])))
    return events


def test_stream_sends_steps_then_reply_with_sources(make_client):
    http = make_client([
        make_message("tool_use", SimpleNamespace(type="tool_use", id="t1", name="search_knowledge_base",
                                                 input={"query": "livraison Suisse"})),
        make_message("end_turn", SimpleNamespace(
            type="text", text="Non, nous ne livrons pas en Suisse.\n\nSources : livraison")),
    ])
    conversation_id = http.post("/api/conversations").json()["id"]
    response = http.post(f"/api/conversations/{conversation_id}/messages",
                         json={"question": "Livrez-vous en Suisse ?"})
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_events(response.text)
    assert events[0] == ("tool", {"name": "search_knowledge_base",
                                  "label": "Recherche dans la documentation…"})
    event_type, reply = events[-1]
    assert event_type == "reply"
    assert reply["text"] == "Non, nous ne livrons pas en Suisse."  # ligne « Sources » retirée
    assert reply["sources"][0]["id"] == "livraison" and reply["sources"][0]["type"] == "document"


def test_unknown_conversation(make_client):
    http = make_client([])
    assert http.post("/api/conversations/unknown/messages", json={"question": "?"}).status_code == 404


def test_message_rate_limit_per_ip(make_client):
    hello = SimpleNamespace(type="text", text="Bonjour !")
    http = make_client([make_message("end_turn", hello) for _ in range(20)])
    conversation_id = http.post("/api/conversations").json()["id"]
    statuses = [http.post(f"/api/conversations/{conversation_id}/messages",
                          json={"question": "Bonjour"}).status_code for _ in range(11)]
    assert statuses[:10] == [200] * 10 and statuses[10] == 429


def test_get_source(make_client):
    http = make_client([])
    source = http.get("/api/sources/livraison").json()
    assert source["title"].startswith("Livraison") and "Belgique" in source["content"]
    assert http.get("/api/sources/missing").status_code == 404


def test_health(make_client):
    http = make_client([])
    assert http.get("/api/health").json()["status"] == "ok"
