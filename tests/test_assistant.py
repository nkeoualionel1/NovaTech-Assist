"""Tests de l'assistant sans appeler l'API Claude (un faux client rejoue des réponses)."""

from types import SimpleNamespace

import pytest

from novatech.assistant.agent import Assistant
from test_retrieval import base


@pytest.fixture(scope="module")
def outils():
    assistant = Assistant(client=SimpleNamespace(), journaliser=False)
    yield assistant.outils
    assistant.recherche.fermer()


# --- Outils (base requise) --------------------------------------------------------------

@base
def test_suivi_commande_avec_le_bon_email(outils):
    r = outils.suivi_commande("cmd-20173", " Thomas.David@example.com ")
    assert r["numero_suivi"] == "6A94612625770"
    assert "adresse_livraison" not in r


@base
def test_suivi_commande_ne_revele_rien_si_email_faux_ou_commande_inconnue(outils):
    mauvais_email = outils.suivi_commande("CMD-20173", "inconnu.personne@example.com")
    inexistante = outils.suivi_commande("CMD-99999", "thomas.david@example.com")
    assert mauvais_email == inexistante  # impossible de deviner si la commande existe
    assert "6A94612625770" not in str(mauvais_email)


@base
def test_verifier_stock_rupture_avec_date(outils):
    r = outils.verifier_stock("Ryzen 7 7800X3D")
    produit = r["produits"][0]
    assert produit["reference"] == "NT-CPU-003"
    assert produit["disponibilite"] == "rupture de stock"
    assert produit["date_reapprovisionnement_prevue"] == "2026-11-12"


@base
def test_verifier_stock_par_reference_et_produit_inconnu(outils):
    assert outils.verifier_stock("nt-lap-001")["produits"][0]["disponibilite"] == "en stock"
    assert "erreur" in outils.verifier_stock("iPhone 17")


@base
def test_transfert_conseiller_ouvert_le_vendredi_midi(outils):
    r = outils.transferer_conseiller("demande_client", "Le client veut parler à un humain.")
    assert r["reference_demande"].startswith("DEM-")
    assert r["conseillers_disponibles_maintenant"] is True  # date de référence : vendredi 12h


@base
def test_outil_inconnu_renvoie_une_erreur(outils):
    resultat, erreur = outils.executer("supprimer_base", {})
    assert erreur


# --- Boucle d'agent avec un faux Claude -------------------------------------------------------

class FauxClaude:
    """Rejoue une liste de réponses et mémorise les requêtes reçues."""

    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.requetes = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requetes.append(kwargs)
        return self.reponses.pop(0)


def _message(stop_reason, *blocs):
    usage = SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0)
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocs), usage=usage)


@base
def test_boucle_execute_l_outil_puis_repond():
    faux = FauxClaude([
        _message("tool_use", SimpleNamespace(type="tool_use", id="t1", name="verifier_stock",
                                             input={"produit": "Orbis Gamer 16"})),
        _message("end_turn", SimpleNamespace(type="text", text="Il est en rupture.")),
    ])
    assistant = Assistant(client=faux, journaliser=False)
    try:
        reponse = assistant.nouvelle_conversation().envoyer("L'Orbis Gamer 16 est en stock ?")
    finally:
        assistant.recherche.fermer()

    assert reponse.texte == "Il est en rupture."
    assert [a.nom for a in reponse.appels] == ["verifier_stock"]
    # Historique : question, appel d'outil, résultat de l'outil (rattaché au bon identifiant), réponse.
    messages = faux.requetes[1]["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    resultat = messages[2]["content"][0]
    assert resultat["tool_use_id"] == "t1" and "rupture" in resultat["content"]
    assert reponse.usage["input_tokens"] == 20
