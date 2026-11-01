"""Lance l'ingestion complète.

Usage :
    python -m novatech.ingestion              # lecture, découpage, vectorisation, écriture en base
    python -m novatech.ingestion --dry-run    # lecture et découpage seulement (ni modèle, ni base)
    python -m novatech.ingestion --dry-run --export chunks.jsonl
"""

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from ..config import get_settings
from .documents import charger_documents
from .produits import charger_produits


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # accents et symboles dans la console Windows
    parser = argparse.ArgumentParser(description="Ingestion des données NovaTech")
    parser.add_argument("--dry-run", action="store_true", help="ne charge ni le modèle ni la base")
    parser.add_argument("--export", type=Path, help="écrit les passages dans un fichier JSONL")
    args = parser.parse_args()

    settings = get_settings()
    debut = time.perf_counter()

    chunks = charger_documents(settings.data_dir / "documents")
    chunks += charger_produits(settings.data_dir / "catalogue" / "produits.json")

    ids = Counter(c.id for c in chunks)
    doublons = [i for i, n in ids.items() if n > 1]
    if doublons:
        print(f"Identifiants en double : {doublons}")
        return 1

    mots = [len(c.texte_a_vectoriser().split()) for c in chunks]
    print(f"{len(chunks)} passages créés à partir de {len({c.source_id for c in chunks})} sources")
    for type_, n in sorted(Counter(c.doc_type for c in chunks).items()):
        print(f"  {type_:<16} {n:>4}")
    print(f"Taille : {min(mots)} à {max(mots)} mots, moyenne {sum(mots) // len(mots)}")

    if args.export:
        with args.export.open("w", encoding="utf-8") as f:
            for c in chunks:
                f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")
        print(f"Passages exportés dans {args.export}")

    if args.dry_run:
        return 0

    from .embeddings import Embedder
    from .store import reconstruire_index

    print(f"Vectorisation avec {settings.embedding_model}…")
    vecteurs = Embedder(settings).embed_passages([c.texte_a_vectoriser() for c in chunks])

    print("Écriture dans PostgreSQL…")
    reconstruire_index(settings.database_url, chunks, vecteurs, settings.embedding_model)
    print(f"Terminé en {time.perf_counter() - debut:.0f} s : {len(chunks)} passages indexés.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
