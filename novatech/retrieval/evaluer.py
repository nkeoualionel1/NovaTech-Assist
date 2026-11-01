"""Mesure la qualité de la recherche sur le jeu de test.

Pour chaque question dont les sources attendues sont indexées (documents ou produits),
on regarde à quel rang apparaît le premier passage issu d'une bonne source.

- Succès@1 : la bonne source est en 1re position
- Succès@5 : la bonne source est dans les 5 premiers passages (ceux envoyés au LLM)
- MRR : moyenne de 1/rang (1 = parfait, 0 = jamais trouvé)

Usage : python -m novatech.retrieval.evaluer [--k 5] [--details]
"""

import argparse
import json
import sys

from .search import Recherche


def charger_questions(recherche: Recherche) -> list[dict]:
    chemin = recherche.settings.data_dir.parent / "evaluation" / "questions_test.json"
    questions = json.loads(chemin.read_text(encoding="utf-8"))
    indexees = {l[0] for l in recherche.conn.execute("SELECT DISTINCT source_id FROM chunks")}
    retenues = []
    for q in questions:
        # Les numéros de commande (CMD-…) relèvent de l'outil suivi_commande, pas de la recherche.
        attendues = [s for s in q["sources_attendues"] if s in indexees]
        if attendues:
            retenues.append({**q, "sources_attendues": attendues})
    return retenues


def evaluer(recherche: Recherche, questions: list[dict], mode: str, k: int) -> dict:
    succes1 = succesk = rr = 0.0
    echecs = []
    for q in questions:
        resultats = recherche.rechercher(q["question"], k=k, mode=mode)
        sources = [r.source_id for r in resultats]
        rang = next((i for i, s in enumerate(sources, 1) if s in q["sources_attendues"]), None)
        if rang:
            succes1 += rang == 1
            succesk += 1
            rr += 1 / rang
        else:
            echecs.append((q["id"], q["question"], q["sources_attendues"], sources[:3]))
    n = len(questions)
    return {"succes1": succes1 / n, "succesk": succesk / n, "mrr": rr / n, "echecs": echecs}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--details", action="store_true", help="liste les questions ratées")
    args = parser.parse_args()

    recherche = Recherche()
    questions = charger_questions(recherche)
    print(f"{len(questions)} questions évaluées (k = {args.k})\n")
    print(f"{'Mode':<10}{'Succès@1':>10}{'Succès@' + str(args.k):>10}{'MRR':>8}")
    for mode in ("vecteur", "texte", "hybride"):
        r = evaluer(recherche, questions, mode, args.k)
        print(f"{mode:<10}{r['succes1']:>10.0%}{r['succesk']:>10.0%}{r['mrr']:>8.2f}")
        if args.details:
            for id_, question, attendues, obtenues in r["echecs"]:
                print(f"   ✗ {id_} {question[:60]}… attendu {attendues}, obtenu {obtenues}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
