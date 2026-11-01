"""Configuration lue depuis les variables d'environnement (et le fichier .env)."""

import os
from dataclasses import dataclass
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


def get_settings() -> Settings:
    return Settings(
        data_dir=Path(os.getenv("DATA_DIR", ROOT / "Dataset" / "data")),
        database_url=os.getenv(
            "DATABASE_URL", "postgresql://novatech:novatech@localhost:5432/novatech"
        ),
        embedding_model=os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-base"),
        passage_prefix=os.getenv("EMBEDDING_PASSAGE_PREFIX", "passage: "),
        query_prefix=os.getenv("EMBEDDING_QUERY_PREFIX", "query: "),
    )
