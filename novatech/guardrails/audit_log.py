"""Journal des échanges : sert au suivi (alertes, coûts, outils appelés) et à l'évaluation.

Les questions sont enregistrées APRÈS masquage des données sensibles.
"""

import psycopg
from psycopg.types.json import Jsonb

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversation_log (
    id              BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    conversation_id TEXT NOT NULL,
    question        TEXT NOT NULL,
    answer          TEXT NOT NULL,
    tool_calls      JSONB NOT NULL,
    sources         JSONB NOT NULL,
    alerts          JSONB NOT NULL,
    stop_reason     TEXT,
    usage           JSONB NOT NULL,
    duration_ms     INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS conversation_log_conversation_idx ON conversation_log (conversation_id);
"""


class AuditLog:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn
        conn.execute(SCHEMA)

    def record(self, conversation_id: str, question: str, reply, duration_ms: int) -> None:
        self.conn.execute(
            """INSERT INTO conversation_log (conversation_id, question, answer, tool_calls, sources,
                                             alerts, stop_reason, usage, duration_ms)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            [conversation_id, question, reply.text,
             Jsonb([{"name": c.name, "input": c.input, "is_error": c.is_error}
                    for c in reply.tool_calls]),
             Jsonb(reply.sources), Jsonb(reply.alerts), reply.stop_reason,
             Jsonb(reply.usage), duration_ms],
        )
