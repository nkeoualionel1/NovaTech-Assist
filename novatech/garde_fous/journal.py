"""Journal des échanges : sert au suivi (alertes, coûts, outils appelés) et à l'évaluation.

Les questions sont enregistrées APRÈS masquage des données sensibles.
"""

import psycopg
from psycopg.types.json import Jsonb

SCHEMA = """
CREATE TABLE IF NOT EXISTS journal_echanges (
    id              BIGSERIAL PRIMARY KEY,
    cree_le         TIMESTAMPTZ NOT NULL DEFAULT now(),
    conversation_id TEXT NOT NULL,
    question        TEXT NOT NULL,
    reponse         TEXT NOT NULL,
    outils          JSONB NOT NULL,
    sources         JSONB NOT NULL,
    alertes         JSONB NOT NULL,
    stop_reason     TEXT,
    usage           JSONB NOT NULL,
    duree_ms        INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS journal_conversation_idx ON journal_echanges (conversation_id);
"""


class Journal:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn
        conn.execute(SCHEMA)

    def enregistrer(self, conversation_id: str, question: str, reponse, duree_ms: int) -> None:
        self.conn.execute(
            """INSERT INTO journal_echanges (conversation_id, question, reponse, outils, sources,
                                             alertes, stop_reason, usage, duree_ms)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            [conversation_id, question, reponse.texte,
             Jsonb([{"nom": a.nom, "entree": a.entree, "erreur": a.erreur} for a in reponse.appels]),
             Jsonb(reponse.sources), Jsonb(reponse.alertes), reponse.stop_reason,
             Jsonb(reponse.usage), duree_ms],
        )
