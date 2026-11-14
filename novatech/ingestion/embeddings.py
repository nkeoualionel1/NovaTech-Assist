"""Vectorisation avec un modèle local (sentence-transformers)."""

import logging
import os
import threading
from functools import cached_property
from pathlib import Path

from ..config import Settings

_LOCK = threading.Lock()


def _model_is_cached(name: str) -> bool:
    """Vrai si le modèle Hugging Face est déjà présent dans le cache local."""
    hf_home = Path(os.getenv("HF_HOME", Path.home() / ".cache" / "huggingface"))
    cache = Path(os.getenv("HF_HUB_CACHE", hf_home / "hub"))
    snapshots = cache / f"models--{name.replace('/', '--')}" / "snapshots"
    return any(snapshots.glob("*/config.json"))


class Embedder:
    def __init__(self, settings: Settings):
        self.settings = settings

    @cached_property
    def model(self):
        # Si le modèle est déjà téléchargé, on évite la vérification en ligne au démarrage.
        # À faire AVANT d'importer huggingface_hub, qui lit ce réglage à l'import.
        if _model_is_cached(self.settings.embedding_model):
            os.environ.setdefault("HF_HUB_OFFLINE", "1")

        # Import tardif : le chargement de torch est lent et inutile en mode --dry-run.
        from sentence_transformers import SentenceTransformer
        from transformers.utils import logging as hf_logging

        hf_logging.set_verbosity_error()
        hf_logging.disable_progress_bar()
        for logger_name in ("sentence_transformers", "huggingface_hub"):
            logging.getLogger(logger_name).setLevel(logging.ERROR)
        return SentenceTransformer(self.settings.embedding_model)

    @property
    def dimension(self) -> int:
        return self.model.get_sentence_embedding_dimension()

    def _encode(self, texts: list[str], **kwargs) -> list[list[float]]:
        # Vecteurs normalisés : la similarité cosinus devient un simple produit scalaire.
        # Verrou : l'API traite plusieurs requêtes en parallèle sur le même modèle.
        with _LOCK:
            vectors = self.model.encode(texts, normalize_embeddings=True, **kwargs)
        return vectors.tolist()

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        prefix = self.settings.passage_prefix
        return self._encode([prefix + t for t in texts], batch_size=16, show_progress_bar=True)

    def embed_query(self, question: str) -> list[float]:
        return self._encode([self.settings.query_prefix + question])[0]
