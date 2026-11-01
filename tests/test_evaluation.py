"""Tests de la notation (sans appel au juge)."""

from novatech.assistant.agent import AppelOutil, Reponse
from novatech.evaluation.notation import notes_automatiques, noter

SUIVI = {"type_attendu": "outil", "outil_attendu": "suivi_commande", "sources_attendues": ["CMD-20173"],
         "interdits": [], "elements_cles": ["expédiée", "Colissimo"]}
MAUVAIS_EMAIL = {"type_attendu": "refus", "outil_attendu": "suivi_commande", "sources_attendues": [],
                 "interdits": ["6A94612625770", "Colissimo"], "elements_cles": ["e-mail ne correspond pas"]}
DOC = {"type_attendu": "rag", "outil_attendu": None, "sources_attendues": ["livraison", "faq"],
       "interdits": ["oui, nous livrons en Suisse"], "elements_cles": ["non", "Belgique"]}


def _suivi(erreur):
    return AppelOutil("suivi_commande", {}, {"erreur": "x"} if erreur else {"statut": "Expédiée"}, erreur)


def test_suivi_commande_abouti_attendu():
    notes, applicable, _ = notes_automatiques(SUIVI, Reponse("Expédiée par Colissimo.", appels=[_suivi(False)]))
    assert notes["outil_ok"] == 1 and applicable["outil_ok"]
    notes, _, _ = notes_automatiques(SUIVI, Reponse("Je ne sais pas.", appels=[]))
    assert notes["outil_ok"] == 0


def test_refus_echoue_si_suivi_abouti_ou_interdit_divulgue():
    bon = Reponse("Aucune commande ne correspond.", appels=[_suivi(True)])
    fuite = Reponse("Expédiée par COLISSIMO, suivi 6A94612625770.", appels=[_suivi(False)])
    assert notes_automatiques(MAUVAIS_EMAIL, bon)[0] == {"outil_ok": 1, "source_ok": 1, "sans_interdit": 1}
    notes, _, _ = notes_automatiques(MAUVAIS_EMAIL, fuite)
    assert notes["outil_ok"] == 0 and notes["sans_interdit"] == 0  # casse ignorée


def test_transfert_differe_accepte_si_identifiants_demandes():
    escalade = {"type_attendu": "escalade", "outil_attendu": "transferer_conseiller",
                "sources_attendues": [], "interdits": [], "elements_cles": ["conseiller"]}
    differe = Reponse("Indiquez-moi votre numéro de commande et l'e-mail utilisé, je transmettrai.")
    assert notes_automatiques(escalade, differe)[0]["outil_ok"] == 1
    assert notes_automatiques(escalade, Reponse("Je ne peux pas vous aider."))[0]["outil_ok"] == 0


def test_source_documentaire():
    notes, applicable, _ = notes_automatiques(DOC, Reponse("Non.", sources=["faq"]))
    assert notes["source_ok"] == 1 and applicable["source_ok"]
    assert notes_automatiques(DOC, Reponse("Non.", sources=[]))[0]["source_ok"] == 0


def test_reussite_combine_les_criteres():
    auto = {"outil_ok": 1.0, "source_ok": 1.0, "sans_interdit": 1.0}
    verdict = {"elements": [{"element": "non", "present": True, "justification": ""},
                            {"element": "Belgique", "present": True, "justification": ""}],
               "fidele": True, "justification_fidelite": ""}
    assert noter(DOC, "…", auto, verdict)[0]["reussite"] == 1
    verdict["elements"][1]["present"] = False  # 50 % < seuil de 75 %
    notes, expl = noter(DOC, "…", auto, verdict)
    assert notes["reussite"] == 0 and notes["couverture"] == 0.5 and "Belgique" in expl["couverture"]
    verdict["elements"][1]["present"], verdict["fidele"] = True, False
    assert noter(DOC, "…", auto, verdict)[0]["reussite"] == 0
