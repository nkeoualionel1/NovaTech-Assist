"""Stockage des passages et de leurs vecteurs dans PostgreSQL + pgvector."""

import psycopg
from pgvector.psycopg import register_vector
from psycopg.types.json import Jsonb

from .models import Chunk

# La colonne tsv sert à la recherche par mots-clés (recherche hybride, phase 4).
SCHEMA = """
CREATE TABLE chunks (
    id          TEXT PRIMARY KEY,
    source_id   TEXT NOT NULL,
    source_type TEXT NOT NULL,
    doc_type    TEXT NOT NULL,
    title       TEXT NOT NULL,
    section     TEXT,
    content     TEXT NOT NULL,
    metadata    JSONB NOT NULL DEFAULT '{{}}',
    embedding   vector({dim}) NOT NULL,
    tsv         tsvector GENERATED ALWAYS AS (
                    to_tsvector('french', title || ' ' || coalesce(section, '') || ' ' || content)
                ) STORED
);
CREATE INDEX chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv);
CREATE INDEX chunks_source_idx ON chunks (source_id);

CREATE TABLE index_info (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def rebuild_index(
    database_url: str, chunks: list[Chunk], vectors: list[list[float]], model_name: str
) -> None:
    """Remplace tout l'index en une seule transaction.

    Si l'ingestion échoue en cours de route, l'ancien index reste intact.
    """
    dim = len(vectors[0])
    with psycopg.connect(database_url) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(conn)
        with conn.transaction():
            conn.execute("DROP TABLE IF EXISTS chunks, index_info")
            conn.execute(SCHEMA.format(dim=dim))
            with conn.cursor() as cur:
                cur.executemany(
                    """INSERT INTO chunks (id, source_id, source_type, doc_type, title,
                                           section, content, metadata, embedding)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    [
                        (c.id, c.source_id, c.source_type, c.doc_type, c.title,
                         c.section, c.content, Jsonb(c.metadata), v)
                        for c, v in zip(chunks, vectors, strict=True)
                    ],
                )
            # Le modèle utilisé est enregistré : la recherche devra utiliser le même.
            conn.execute(
                "INSERT INTO index_info VALUES ('embedding_model', %s), ('dimension', %s), "
                "('chunk_count', %s), ('built_at', now()::text)",
                (model_name, str(dim), str(len(chunks))),
            )
