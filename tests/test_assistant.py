"""Tests de l'assistant sans appeler l'API Claude (un faux client rejoue des réponses)."""

from types import SimpleNamespace

import pytest

from novatech.assistant.agent import Assistant
from test_retrieval import requires_db


@pytest.fixture(scope="module")
def toolbox():
    assistant = Assistant(client=SimpleNamespace(), enable_audit_log=False)
    yield assistant.toolbox
    assistant.retriever.close()


# --- Outils (base requise) --------------------------------------------------------------

@requires_db
def test_track_order_with_matching_email(toolbox):
    result = toolbox.track_order("cmd-20173", " Thomas.David@example.com ")
    assert result["tracking_number"] == "6A94612625770"
    assert "address" not in str(result.keys())


@requires_db
def test_track_order_reveals_nothing_on_wrong_email_or_unknown_order(toolbox):
    wrong_email = toolbox.track_order("CMD-20173", "inconnu.personne@example.com")
    unknown_order = toolbox.track_order("CMD-99999", "thomas.david@example.com")
    assert wrong_email == unknown_order  # impossible de deviner si la commande existe
    assert "6A94612625770" not in str(wrong_email)


@requires_db
def test_check_stock_out_of_stock_with_restock_date(toolbox):
    product = toolbox.check_stock("Ryzen 7 7800X3D")["products"][0]
    assert product["reference"] == "NT-CPU-003"
    assert product["availability"] == "rupture de stock"
    assert product["expected_restock_date"] == "2026-11-12"


@requires_db
def test_check_stock_by_reference_and_unknown_product(toolbox):
    assert toolbox.check_stock("nt-lap-001")["products"][0]["availability"] == "en stock"
    assert "error" in toolbox.check_stock("iPhone 17")


@requires_db
def test_transfer_to_agent_open_on_friday_noon(toolbox):
    result = toolbox.transfer_to_agent("customer_request", "Le client veut parler à un humain.")
    assert result["request_reference"].startswith("DEM-")
    assert result["agents_available_now"] is True  # date de référence : vendredi 12h


@requires_db
def test_unknown_tool_returns_an_error(toolbox):
    _, is_error = toolbox.execute("drop_database", {})
    assert is_error


# --- Boucle d'agent avec un faux Claude -------------------------------------------------------

class FakeClaude:
    """Rejoue une liste de réponses et mémorise les requêtes reçues."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        return self.replies.pop(0)


def make_message(stop_reason, *blocks):
    usage = SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0)
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocks), usage=usage)


@requires_db
def test_loop_runs_the_tool_then_answers():
    fake = FakeClaude([
        make_message("tool_use", SimpleNamespace(type="tool_use", id="t1", name="check_stock",
                                                 input={"product": "Orbis Gamer 16"})),
        make_message("end_turn", SimpleNamespace(type="text", text="Il est en rupture.")),
    ])
    assistant = Assistant(client=fake, enable_audit_log=False)
    try:
        reply = assistant.new_conversation().send("L'Orbis Gamer 16 est en stock ?")
    finally:
        assistant.retriever.close()

    assert reply.text == "Il est en rupture."
    assert [c.name for c in reply.tool_calls] == ["check_stock"]
    # Historique : question, appel d'outil, résultat de l'outil (rattaché au bon identifiant), réponse.
    messages = fake.requests[1]["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    tool_result = messages[2]["content"][0]
    assert tool_result["tool_use_id"] == "t1" and "rupture" in tool_result["content"]
    assert reply.usage["input_tokens"] == 20
