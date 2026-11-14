"""Lance l'ingestion complète.

Usage :
    python -m novatech.ingestion              # lecture, découpage, vectorisation, écriture en base
    python -m novatech.ingestion --dry-run    # lecture et découpage seulement (ni modèle, ni base)
    python -m novatech.ingestion --dry-run --export chunks.jsonl
    python -m novatech.ingestion --shop-only  # recharge seulement les tables products / orders
"""

import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from ..config import get_settings
from .documents import load_documents
from .products import load_products


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # accents et symboles dans la console Windows
    parser = argparse.ArgumentParser(description="Ingestion des données NovaTech")
    parser.add_argument("--dry-run", action="store_true", help="ne charge ni le modèle ni la base")
    parser.add_argument("--export", type=Path, help="écrit les passages dans un fichier JSONL")
    parser.add_argument("--shop-only", action="store_true",
                        help="recharge seulement les tables products/orders (sans vectorisation)")
    args = parser.parse_args()

    settings = get_settings()
    start = time.perf_counter()

    if args.shop_only:
        return _load_shop(settings)

    chunks = load_documents(settings.data_dir / "documents")
    chunks += load_products(settings.data_dir / "catalogue" / "produits.json")

    id_counts = Counter(c.id for c in chunks)
    duplicates = [i for i, n in id_counts.items() if n > 1]
    if duplicates:
        print(f"Identifiants en double : {duplicates}")
        return 1

    word_counts = [len(c.text_to_embed().split()) for c in chunks]
    print(f"{len(chunks)} passages créés à partir de {len({c.source_id for c in chunks})} sources")
    for doc_type, n in sorted(Counter(c.doc_type for c in chunks).items()):
        print(f"  {doc_type:<16} {n:>4}")
    print(f"Taille : {min(word_counts)} à {max(word_counts)} mots, "
          f"moyenne {sum(word_counts) // len(word_counts)}")

    if args.export:
        with args.export.open("w", encoding="utf-8") as f:
            for c in chunks:
                f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")
        print(f"Passages exportés dans {args.export}")

    if args.dry_run:
        return 0

    from .embeddings import Embedder
    from .store import rebuild_index

    print(f"Vectorisation avec {settings.embedding_model}…")
    vectors = Embedder(settings).embed_passages([c.text_to_embed() for c in chunks])

    print("Écriture dans PostgreSQL…")
    rebuild_index(settings.database_url, chunks, vectors, settings.embedding_model)
    print(f"Terminé en {time.perf_counter() - start:.0f} s : {len(chunks)} passages indexés.")
    return _load_shop(settings)


def _load_shop(settings) -> int:
    from .shop_data import load_shop_tables

    product_count, order_count = load_shop_tables(settings.database_url, settings.data_dir)
    print(f"Tables magasin chargées : {product_count} produits, {order_count} commandes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
