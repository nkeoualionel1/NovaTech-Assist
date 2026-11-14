"""Tests de la notation (sans appel au juge). Les cas reprennent le format du jeu de test."""

from novatech.assistant.agent import Reply, ToolCall
from novatech.evaluation.grading import automatic_grades, combine_grades

ORDER_CASE = {"type_attendu": "outil", "outil_attendu": "suivi_commande", "sources_attendues": ["CMD-20173"],
              "interdits": [], "elements_cles": ["expédiée", "Colissimo"]}
WRONG_EMAIL_CASE = {"type_attendu": "refus", "outil_attendu": "suivi_commande", "sources_attendues": [],
                    "interdits": ["6A94612625770", "Colissimo"],
                    "elements_cles": ["e-mail ne correspond pas"]}
DOC_CASE = {"type_attendu": "rag", "outil_attendu": None, "sources_attendues": ["livraison", "faq"],
            "interdits": ["oui, nous livrons en Suisse"], "elements_cles": ["non", "Belgique"]}


def _track_order(is_error):
    result = {"error": "x"} if is_error else {"status": "Expédiée"}
    return ToolCall("track_order", {}, result, is_error)


def test_successful_order_lookup_expected():
    grades, applicable, _ = automatic_grades(
        ORDER_CASE, Reply("Expédiée par Colissimo.", tool_calls=[_track_order(False)]))
    assert grades["tool_ok"] == 1 and applicable["tool_ok"]
    grades, _, _ = automatic_grades(ORDER_CASE, Reply("Je ne sais pas.", tool_calls=[]))
    assert grades["tool_ok"] == 0


def test_refusal_fails_if_order_found_or_forbidden_text_leaked():
    good = Reply("Aucune commande ne correspond.", tool_calls=[_track_order(True)])
    leak = Reply("Expédiée par COLISSIMO, suivi 6A94612625770.", tool_calls=[_track_order(False)])
    assert automatic_grades(WRONG_EMAIL_CASE, good)[0] == {"tool_ok": 1, "source_ok": 1, "no_forbidden": 1}
    grades, _, _ = automatic_grades(WRONG_EMAIL_CASE, leak)
    assert grades["tool_ok"] == 0 and grades["no_forbidden"] == 0  # casse ignorée


def test_deferred_handoff_accepted_when_identifiers_requested():
    escalation = {"type_attendu": "escalade", "outil_attendu": "transferer_conseiller",
                  "sources_attendues": [], "interdits": [], "elements_cles": ["conseiller"]}
    deferred = Reply("Indiquez-moi votre numéro de commande et l'e-mail utilisé, je transmettrai.")
    assert automatic_grades(escalation, deferred)[0]["tool_ok"] == 1
    assert automatic_grades(escalation, Reply("Je ne peux pas vous aider."))[0]["tool_ok"] == 0


def test_documentary_source():
    grades, applicable, _ = automatic_grades(DOC_CASE, Reply("Non.", sources=["faq"]))
    assert grades["source_ok"] == 1 and applicable["source_ok"]
    assert automatic_grades(DOC_CASE, Reply("Non.", sources=[]))[0]["source_ok"] == 0


def test_success_combines_all_criteria():
    auto = {"tool_ok": 1.0, "source_ok": 1.0, "no_forbidden": 1.0}
    verdict = {"items": [{"element": "non", "present": True, "justification": ""},
                         {"element": "Belgique", "present": True, "justification": ""}],
               "faithful": True, "faithfulness_justification": ""}
    assert combine_grades(auto, verdict)[0]["success"] == 1
    verdict["items"][1]["present"] = False  # 50 % < seuil de 75 %
    grades, explanations = combine_grades(auto, verdict)
    assert grades["success"] == 0 and grades["coverage"] == 0.5 and "Belgique" in explanations["coverage"]
    verdict["items"][1]["present"], verdict["faithful"] = True, False
    assert combine_grades(auto, verdict)[0]["success"] == 0
