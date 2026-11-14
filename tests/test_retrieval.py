import psycopg
import pytest

from novatech.config import get_settings
from novatech.retrieval.search import Retriever, rrf_fusion


def test_rrf_favors_chunks_present_in_both_rankings():
    scores, ranks = rrf_fusion({"vector": ["a", "b", "c"], "text": ["c", "d"]})
    ranking = sorted(scores, key=scores.get, reverse=True)
    assert ranking[0] == "c"  # 3e et 1er : bat « a », 1er dans une seule liste
    assert ranks["c"] == {"vector": 3, "text": 1}
    assert set(ranking) == {"a", "b", "c", "d"}


def test_unknown_filter_rejected():
    with pytest.raises(ValueError):
        Retriever._where({"prix; DROP TABLE chunks": "x"})


# Tests d'intégration : nécessitent la base démarrée (docker compose up -d) et indexée.
def _database_ready() -> bool:
    try:
        with psycopg.connect(get_settings().database_url, connect_timeout=2) as conn:
            return conn.execute("SELECT to_regclass('chunks')").fetchone()[0] is not None
    except psycopg.OperationalError:
        return False


requires_db = pytest.mark.skipif(not _database_ready(), reason="base PostgreSQL indisponible")


@pytest.fixture(scope="module")
def retriever():
    r = Retriever()
    yield r
    r.close()


@requires_db
def test_delivery_question(retriever):
    results = retriever.search("Est-ce que vous livrez en Suisse ?")
    assert {"livraison", "faq"} & {r.source_id for r in results[:3]}


@requires_db
def test_exact_product_reference(retriever):
    results = retriever.search("Le Ryzen 7 7800X3D est-il compatible DDR4 ?", k=3)
    assert "NT-CPU-003" in [r.source_id for r in results]


@requires_db
def test_product_filter(retriever):
    results = retriever.search("portable léger", filters={"source_type": "product"})
    assert results and all(r.source_type == "product" for r in results)


@requires_db
def test_category_filter(retriever):
    results = retriever.search("processeur pas cher", filters={"category": "Processeur"})
    assert results and all(r.metadata["category"] == "Processeur" for r in results)
