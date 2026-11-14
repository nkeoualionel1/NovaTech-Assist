"""Recherche hybride : vecteurs (sens) + plein texte (mots-clés), fusionnés par RRF."""

from .search import Retriever, SearchResult

__all__ = ["Retriever", "SearchResult"]
