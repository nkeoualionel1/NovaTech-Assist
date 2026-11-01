import psycopg
import pytest

from novatech.config import get_settings
from novatech.retrieval.search import Recherche, fusion_rrf


def test_fusion_rrf_favorise_les_passages_presents_dans_les_deux_listes():
    scores, rangs = fusion_rrf({"vecteur": ["a", "b", "c"], "texte": ["c", "d"]})
    classement = sorted(scores, key=scores.get, reverse=True)
    assert classement[0] == "c"  # 3e et 1er : bat « a », 1er dans une seule liste
    assert rangs["c"] == {"vecteur": 3, "texte": 1}
    assert set(classement) == {"a", "b", "c", "d"}


def test_filtre_inconnu_refuse():
    with pytest.raises(ValueError):
        Recherche._where({"prix; DROP TABLE chunks": "x"})


# Tests d'intégration : nécessitent la base démarrée (docker compose up -d) et indexée.
def _base_disponible() -> bool:
    try:
        with psycopg.connect(get_settings().database_url, connect_timeout=2) as conn:
            return conn.execute("SELECT to_regclass('chunks')").fetchone()[0] is not None
    except psycopg.OperationalError:
        return False


base = pytest.mark.skipif(not _base_disponible(), reason="base PostgreSQL indisponible")


@pytest.fixture(scope="module")
def recherche():
    r = Recherche()
    yield r
    r.fermer()


@base
def test_question_de_livraison(recherche):
    resultats = recherche.rechercher("Est-ce que vous livrez en Suisse ?")
    assert {"livraison", "faq"} & {r.source_id for r in resultats[:3]}


@base
def test_reference_produit_exacte(recherche):
    resultats = recherche.rechercher("Le Ryzen 7 7800X3D est-il compatible DDR4 ?", k=3)
    assert "NT-CPU-003" in [r.source_id for r in resultats]


@base
def test_filtre_produits(recherche):
    resultats = recherche.rechercher("portable léger", filtres={"source_type": "produit"})
    assert resultats and all(r.source_type == "produit" for r in resultats)
