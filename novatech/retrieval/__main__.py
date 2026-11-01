"""Teste une question depuis le terminal.

Usage :
    python -m novatech.retrieval "Est-ce que vous livrez en Suisse ?"
    python -m novatech.retrieval "processeur pas cher" --k 3 --filtre source_type=produit
    python -m novatech.retrieval "garantie écran" --mode vecteur
"""

import argparse
import sys

from .search import Recherche


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Recherche hybride NovaTech")
    parser.add_argument("question")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--mode", choices=["hybride", "vecteur", "texte"], default="hybride")
    parser.add_argument("--filtre", action="append", default=[], metavar="CLE=VALEUR")
    parser.add_argument("--complet", action="store_true", help="affiche le texte entier des passages")
    args = parser.parse_args()

    filtres = dict(f.split("=", 1) for f in args.filtre)
    recherche = Recherche()
    for i, r in enumerate(recherche.rechercher(args.question, args.k, filtres, args.mode), start=1):
        rangs = ", ".join(f"{nom} n°{rang}" for nom, rang in r.rangs.items())
        print(f"\n{i}. [{r.source_id}] {r.titre}" + (f" — {r.section}" if r.section else ""))
        print(f"   score {r.score}  ({rangs})")
        texte = r.contenu if args.complet else r.contenu[:200].replace("\n", " ") + "…"
        print("   " + texte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
