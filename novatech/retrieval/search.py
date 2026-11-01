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
NB_CANDIDATS = 30  # passages récupérés par chaque recherche avant fusion
FILTRES_AUTORISES = {
    "source_type": "source_type = %s",
    "doc_type": "doc_type = %s",
    "categorie": "metadata->>'categorie' = %s",
    "source_id": "source_id = %s",
}


def fusion_rrf(listes: dict[str, list[str]], k: int = RRF_K) -> tuple[dict, dict]:
    """Fusionne des classements : score = somme de 1 / (k + rang) sur chaque liste."""
    scores, rangs = {}, {}
    for nom, ids in listes.items():
        for rang, id_ in enumerate(ids, start=1):
            scores[id_] = scores.get(id_, 0.0) + 1 / (k + rang)
            rangs.setdefault(id_, {})[nom] = rang
    return scores, rangs


@dataclass
class Resultat:
    id: str
    source_id: str
    source_type: str
    doc_type: str
    titre: str
    section: str | None
    contenu: str
    metadata: dict
    score: float = 0.0
    rangs: dict = field(default_factory=dict)  # rang dans chaque recherche, pour le débogage


class Recherche:
    """À créer une seule fois : charge le modèle et garde la connexion ouverte."""

    def __init__(self, settings: Settings | None = None, conn: psycopg.Connection | None = None):
        self.settings = settings or get_settings()
        self.embedder = Embedder(self.settings)
        self.conn = conn or psycopg.connect(self.settings.database_url, autocommit=True)
        register_vector(self.conn)
        self._verifier_modele()

    def _verifier_modele(self) -> None:
        """La question doit être vectorisée avec le même modèle que les passages."""
        ligne = self.conn.execute(
            "SELECT valeur FROM index_info WHERE cle = 'embedding_model'"
        ).fetchone()
        if ligne is None:
            raise RuntimeError("Index vide : lancez d'abord python -m novatech.ingestion")
        if ligne[0] != self.settings.embedding_model:
            raise RuntimeError(
                f"L'index a été construit avec {ligne[0]} mais la configuration demande "
                f"{self.settings.embedding_model} : relancez l'ingestion."
            )

    @staticmethod
    def _where(filtres: dict | None) -> tuple[str, list]:
        if not filtres:
            return "", []
        inconnus = set(filtres) - set(FILTRES_AUTORISES)
        if inconnus:
            raise ValueError(f"Filtres inconnus : {inconnus}")
        clauses = [FILTRES_AUTORISES[cle] for cle in filtres]
        return " AND " + " AND ".join(clauses), list(filtres.values())

    def recherche_vectorielle(self, question: str, n: int = NB_CANDIDATS, filtres=None) -> list[str]:
        vecteur = Vector(self.embedder.embed_query(question))
        where, params = self._where(filtres)
        lignes = self.conn.execute(
            f"SELECT id FROM chunks WHERE TRUE {where} ORDER BY embedding <=> %s LIMIT %s",
            [*params, vecteur, n],
        ).fetchall()
        return [l[0] for l in lignes]

    def recherche_texte(self, question: str, n: int = NB_CANDIDATS, filtres=None) -> list[str]:
        # plainto_tsquery relie les mots par ET : une question en langage naturel ne trouverait
        # presque rien. On remplace les ET par des OU ; ts_rank_cd favorise ensuite les passages
        # qui contiennent le plus de mots de la question, et les plus rapprochés.
        where, params = self._where(filtres)
        lignes = self.conn.execute(
            f"""WITH q AS (
                    SELECT replace(plainto_tsquery('french', %s)::text, '&', '|')::tsquery AS q
                )
                SELECT id FROM chunks, q
                WHERE tsv @@ q.q {where}
                ORDER BY ts_rank_cd(tsv, q.q) DESC
                LIMIT %s""",
            [question, *params, n],
        ).fetchall()
        return [l[0] for l in lignes]

    def rechercher(self, question: str, k: int = 5, filtres: dict | None = None,
                   mode: str = "hybride") -> list[Resultat]:
        """Renvoie les k passages les plus pertinents.

        mode : "hybride" (par défaut), "vecteur" ou "texte" (utile pour comparer).
        filtres : ex. {"source_type": "produit"} ou {"categorie": "Processeur"}.
        """
        listes = {}
        if mode in ("hybride", "vecteur"):
            listes["vecteur"] = self.recherche_vectorielle(question, filtres=filtres)
        if mode in ("hybride", "texte"):
            listes["texte"] = self.recherche_texte(question, filtres=filtres)
        if not listes:
            raise ValueError(f"Mode inconnu : {mode}")

        scores, rangs = fusion_rrf(listes)
        meilleurs = sorted(scores, key=scores.get, reverse=True)[:k]
        return self._charger(meilleurs, scores, rangs)

    def _charger(self, ids: list[str], scores: dict, rangs: dict) -> list[Resultat]:
        if not ids:
            return []
        with self.conn.cursor(row_factory=dict_row) as cur:
            lignes = cur.execute(
                """SELECT id, source_id, source_type, doc_type, titre, section, contenu, metadata
                   FROM chunks WHERE id = ANY(%s)""",
                [ids],
            ).fetchall()
        par_id = {l["id"]: l for l in lignes}
        return [
            Resultat(**par_id[i], score=round(scores[i], 5), rangs=rangs[i])
            for i in ids
            if i in par_id
        ]

    def fermer(self) -> None:
        self.conn.close()
