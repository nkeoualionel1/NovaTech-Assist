"""Mesure la qualité de la recherche sur le jeu de test.

Pour chaque question dont les sources attendues sont indexées (documents ou produits),
on regarde à quel rang apparaît le premier passage issu d'une bonne source.

- Succès@1 : la bonne source est en 1re position
- Succès@5 : la bonne source est dans les 5 premiers passages (ceux envoyés au LLM)
- MRR : moyenne de 1/rang (1 = parfait, 0 = jamais trouvé)

Usage : python -m novatech.retrieval.evaluate [--k 5] [--details]
"""

import argparse
import json
import sys

from .search import Retriever


def load_questions(retriever: Retriever) -> list[dict]:
    path = retriever.settings.data_dir.parent / "evaluation" / "questions_test.json"
    questions = json.loads(path.read_text(encoding="utf-8"))
    indexed = {row[0] for row in retriever.conn.execute("SELECT DISTINCT source_id FROM chunks")}
    kept = []
    for q in questions:
        # Les numéros de commande (CMD-…) relèvent de l'outil track_order, pas de la recherche.
        expected = [s for s in q["sources_attendues"] if s in indexed]
        if expected:
            kept.append({**q, "sources_attendues": expected})
    return kept


def evaluate(retriever: Retriever, questions: list[dict], mode: str, k: int) -> dict:
    hits_at_1 = hits_at_k = reciprocal_rank_sum = 0.0
    misses = []
    for q in questions:
        results = retriever.search(q["question"], k=k, mode=mode)
        sources = [r.source_id for r in results]
        rank = next((i for i, s in enumerate(sources, 1) if s in q["sources_attendues"]), None)
        if rank:
            hits_at_1 += rank == 1
            hits_at_k += 1
            reciprocal_rank_sum += 1 / rank
        else:
            misses.append((q["id"], q["question"], q["sources_attendues"], sources[:3]))
    n = len(questions)
    return {"hit_at_1": hits_at_1 / n, "hit_at_k": hits_at_k / n,
            "mrr": reciprocal_rank_sum / n, "misses": misses}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--details", action="store_true", help="liste les questions ratées")
    args = parser.parse_args()

    retriever = Retriever()
    questions = load_questions(retriever)
    print(f"{len(questions)} questions évaluées (k = {args.k})\n")
    print(f"{'Mode':<10}{'Succès@1':>10}{'Succès@' + str(args.k):>10}{'MRR':>8}")
    for mode in ("vector", "text", "hybrid"):
        r = evaluate(retriever, questions, mode, args.k)
        print(f"{mode:<10}{r['hit_at_1']:>10.0%}{r['hit_at_k']:>10.0%}{r['mrr']:>8.2f}")
        if args.details:
            for case_id, question, expected, got in r["misses"]:
                print(f"   ✗ {case_id} {question[:60]}… attendu {expected}, obtenu {got}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
