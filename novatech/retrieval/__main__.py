"""Teste une question depuis le terminal.

Usage :
    python -m novatech.retrieval "Est-ce que vous livrez en Suisse ?"
    python -m novatech.retrieval "processeur pas cher" --k 3 --filter source_type=product
    python -m novatech.retrieval "garantie écran" --mode vector
"""

import argparse
import sys

from .search import SEARCH_MODES, Retriever


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Recherche hybride NovaTech")
    parser.add_argument("question")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--mode", choices=SEARCH_MODES, default="hybrid")
    parser.add_argument("--filter", action="append", default=[], metavar="CLE=VALEUR")
    parser.add_argument("--full", action="store_true", help="affiche le texte entier des passages")
    args = parser.parse_args()

    filters = dict(f.split("=", 1) for f in args.filter)
    retriever = Retriever()
    for i, r in enumerate(retriever.search(args.question, args.k, filters, args.mode), start=1):
        ranks = ", ".join(f"{name} n°{rank}" for name, rank in r.ranks.items())
        print(f"\n{i}. [{r.source_id}] {r.title}" + (f" — {r.section}" if r.section else ""))
        print(f"   score {r.score}  ({ranks})")
        text = r.content if args.full else r.content[:200].replace("\n", " ") + "…"
        print("   " + text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
