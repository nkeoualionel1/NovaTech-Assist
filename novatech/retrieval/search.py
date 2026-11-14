"""Recherche hybride dans la table chunks.

Deux recherches complémentaires sont lancées :
- vectorielle : retrouve les passages proches par le SENS (« livrer en Suisse » ≈ « zones de livraison ») ;
- plein texte : retrouve les MOTS exacts (références produit, « 7800X3D », « NovaCare+ »…).

Leurs classements sont fusionnés par Reciprocal Rank Fusion (RRF) : chaque passage reçoit
1 / (k + rang) pour chaque liste où il apparaît. Un passage bien classé dans les deux
listes remonte en tête, sans avoir à comparer des scores de natures différentes.
"""

from dataclasses import dataclass, field

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from ..config import Settings, get_settings
from ..ingestion.embeddings import Embedder

RRF_K = 60  # valeur standard : atténue l'écart entre le 1er et le 2e rang
CANDIDATES_PER_SEARCH = 30  # passages récupérés par chaque recherche avant fusion
ALLOWED_FILTERS = {
    "source_type": "source_type = %s",
    "doc_type": "doc_type = %s",
    "category": "metadata->>'category' = %s",
    "source_id": "source_id = %s",
}
SEARCH_MODES = ("hybrid", "vector", "text")


def rrf_fusion(rankings: dict[str, list[str]], k: int = RRF_K) -> tuple[dict, dict]:
    """Fusionne des classements : score = somme de 1 / (k + rang) sur chaque liste."""
    scores, ranks = {}, {}
    for ranking_name, ids in rankings.items():
        for rank, chunk_id in enumerate(ids, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1 / (k + rank)
            ranks.setdefault(chunk_id, {})[ranking_name] = rank
    return scores, ranks


@dataclass
class SearchResult:
    id: str
    source_id: str
    source_type: str
    doc_type: str
    title: str
    section: str | None
    content: str
    metadata: dict
    score: float = 0.0
    ranks: dict = field(default_factory=dict)  # rang dans chaque recherche, pour le débogage


class Retriever:
    """À créer une seule fois : charge le modèle et garde la connexion ouverte."""

    def __init__(self, settings: Settings | None = None, conn: psycopg.Connection | None = None):
        self.settings = settings or get_settings()
        self.embedder = Embedder(self.settings)
        self.conn = conn or psycopg.connect(self.settings.database_url, autocommit=True)
        register_vector(self.conn)
        self._check_index_model()

    def _check_index_model(self) -> None:
        """La question doit être vectorisée avec le même modèle que les passages."""
        row = self.conn.execute(
            "SELECT value FROM index_info WHERE key = 'embedding_model'"
        ).fetchone()
        if row is None:
            raise RuntimeError("Index vide : lancez d'abord python -m novatech.ingestion")
        if row[0] != self.settings.embedding_model:
            raise RuntimeError(
                f"L'index a été construit avec {row[0]} mais la configuration demande "
                f"{self.settings.embedding_model} : relancez l'ingestion."
            )

    @staticmethod
    def _where(filters: dict | None) -> tuple[str, list]:
        if not filters:
            return "", []
        unknown = set(filters) - set(ALLOWED_FILTERS)
        if unknown:
            raise ValueError(f"Filtres inconnus : {unknown}")
        clauses = [ALLOWED_FILTERS[key] for key in filters]
        return " AND " + " AND ".join(clauses), list(filters.values())

    def vector_search(self, question: str, n: int = CANDIDATES_PER_SEARCH, filters=None) -> list[str]:
        vector = Vector(self.embedder.embed_query(question))
        where, params = self._where(filters)
        rows = self.conn.execute(
            f"SELECT id FROM chunks WHERE TRUE {where} ORDER BY embedding <=> %s LIMIT %s",
            [*params, vector, n],
        ).fetchall()
        return [row[0] for row in rows]

    def text_search(self, question: str, n: int = CANDIDATES_PER_SEARCH, filters=None) -> list[str]:
        # plainto_tsquery relie les mots par ET : une question en langage naturel ne trouverait
        # presque rien. On remplace les ET par des OU ; ts_rank_cd favorise ensuite les passages
        # qui contiennent le plus de mots de la question, et les plus rapprochés.
        where, params = self._where(filters)
        rows = self.conn.execute(
            f"""WITH q AS (
                    SELECT replace(plainto_tsquery('french', %s)::text, '&', '|')::tsquery AS q
                )
                SELECT id FROM chunks, q
                WHERE tsv @@ q.q {where}
                ORDER BY ts_rank_cd(tsv, q.q) DESC
                LIMIT %s""",
            [question, *params, n],
        ).fetchall()
        return [row[0] for row in rows]

    def search(self, question: str, k: int = 5, filters: dict | None = None,
               mode: str = "hybrid") -> list[SearchResult]:
        """Renvoie les k passages les plus pertinents.

        mode : "hybrid" (par défaut), "vector" ou "text" (utile pour comparer).
        filters : ex. {"source_type": "product"} ou {"category": "Processeur"}.
        """
        rankings = {}
        if mode in ("hybrid", "vector"):
            rankings["vector"] = self.vector_search(question, filters=filters)
        if mode in ("hybrid", "text"):
            rankings["text"] = self.text_search(question, filters=filters)
        if not rankings:
            raise ValueError(f"Mode inconnu : {mode}")

        scores, ranks = rrf_fusion(rankings)
        best_ids = sorted(scores, key=scores.get, reverse=True)[:k]
        return self._load(best_ids, scores, ranks)

    def _load(self, ids: list[str], scores: dict, ranks: dict) -> list[SearchResult]:
        if not ids:
            return []
        with self.conn.cursor(row_factory=dict_row) as cur:
            rows = cur.execute(
                """SELECT id, source_id, source_type, doc_type, title, section, content, metadata
                   FROM chunks WHERE id = ANY(%s)""",
                [ids],
            ).fetchall()
        by_id = {row["id"]: row for row in rows}
        return [
            SearchResult(**by_id[i], score=round(scores[i], 5), ranks=ranks[i])
            for i in ids
            if i in by_id
        ]

    def close(self) -> None:
        self.conn.close()
