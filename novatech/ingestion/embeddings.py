"""Vectorisation avec un modèle local (sentence-transformers)."""

from functools import cached_property

from ..config import Settings


class Embedder:
    def __init__(self, settings: Settings):
        self.settings = settings

    @cached_property
    def model(self):
        # Import tardif : le chargement de torch est lent et inutile en mode --dry-run.
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(self.settings.embedding_model)

    @property
    def dimension(self) -> int:
        return self.model.get_sentence_embedding_dimension()

    def _encode(self, textes: list[str], **kwargs) -> list[list[float]]:
        # Vecteurs normalisés : la similarité cosinus devient un simple produit scalaire.
        vecteurs = self.model.encode(textes, normalize_embeddings=True, **kwargs)
        return vecteurs.tolist()

    def embed_passages(self, textes: list[str]) -> list[list[float]]:
        prefixe = self.settings.passage_prefix
        return self._encode([prefixe + t for t in textes], batch_size=16, show_progress_bar=True)

    def embed_query(self, question: str) -> list[float]:
        return self._encode([self.settings.query_prefix + question])[0]
