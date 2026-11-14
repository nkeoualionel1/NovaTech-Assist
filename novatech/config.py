"""Configuration lue depuis les variables d'environnement (et le fichier .env)."""

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database_url: str
    embedding_model: str
    # Les modèles E5 attendent un préfixe différent pour les passages et les questions.
    passage_prefix: str
    query_prefix: str
    claude_model: str
    claude_effort: str
    # Le jeu de données est figé au 30/10/2026 : l'assistant raisonne à cette date
    # (« ma commande arrive quand ? »). En production, on utiliserait l'heure réelle.
    reference_date: datetime


def get_settings() -> Settings:
    return Settings(
        claude_model=os.getenv("CLAUDE_MODEL", "claude-opus-5-5"),
        claude_effort=os.getenv("CLAUDE_EFFORT", "medium"),
        reference_date=datetime.fromisoformat(os.getenv("REFERENCE_DATE", "2026-10-30T12:00")),
        data_dir=Path(os.getenv("DATA_DIR", ROOT / "Dataset" / "data")),
        database_url=os.getenv(
            "DATABASE_URL", "postgresql://novatech:novatech@localhost:5432/novatech"
        ),
        embedding_model=os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-base"),
        passage_prefix=os.getenv("EMBEDDING_PASSAGE_PREFIX", "passage: "),
        query_prefix=os.getenv("EMBEDDING_QUERY_PREFIX", "query: "),
    )
