"""Évaluation de l'assistant sur les 40 questions sélectionnées (phase 8).

Usage :
    python -m novatech.evaluation                          # variante « baseline », 1 passage
    python -m novatech.evaluation --limit 5                # pilote sur 5 questions
    python -m novatech.evaluation --variant v1 --model claude-opus-5-5 --reps 2
    python -m novatech.evaluation --controle-juge          # vérifie que le juge rejette les mauvaises réponses
    python -m novatech.evaluation --renoter                # renote les réponses existantes (notation modifiée)

Sorties dans .claude/hillclimb/assistant/<variante>/ :
    results.jsonl  une ligne par (question, passage) notée — écrite au fil de l'eau, reprise possible
    errors.jsonl   tentatives sans résultat exploitable (erreur d'API, délai dépassé, juge en échec…)
    traces/        conversation complète de chaque cas
Rapport : node <skill>/shared/evals/report/build-report-lite.mjs .claude/hillclimb/assistant/
"""

import argparse
import dataclasses
import hashlib
import json
import math
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as DelaiDepasse
from pathlib import Path

import anthropic

from ..assistant import Assistant, Reponse
from ..assistant.agent import BETAS, AppelOutil
from ..assistant.prompt import consigne_systeme
from ..config import ROOT, get_settings
from .notation import METRIQUES, contexte_outils, juger, notes_automatiques, noter

FLUX = ROOT / ".claude" / "hillclimb" / "assistant"
SELECTION = ROOT / "Dataset" / "evaluation" / "selection_40.json"
QUESTIONS = ROOT / "Dataset" / "evaluation" / "questions_test.json"
FICHIERS_HARNAIS = [Path(__file__), Path(__file__).with_name("notation.py"), SELECTION, QUESTIONS]
ERREURS_TRANSITOIRES = (anthropic.RateLimitError, anthropic.InternalServerError,
                        anthropic.APIConnectionError)
TENTATIVES_MAX = 4
_ecriture = threading.Lock()


# --- Cas, harnais, fichiers -------------------------------------------------------------

def charger_cas(limite: int | None) -> list[dict]:
    ids = json.loads(SELECTION.read_text(encoding="utf-8"))["ids"]
    toutes = {q["id"]: q for q in json.loads(QUESTIONS.read_text(encoding="utf-8"))}
    return [toutes[i] for i in ids][:limite]


def empreinte_harnais() -> str:
    h = hashlib.sha256()
    for f in sorted(FICHIERS_HARNAIS):
        h.update(f.relative_to(ROOT).as_posix().encode() + b"\0" + f.read_bytes())
    return h.hexdigest()


def verifier_harnais(approuver: bool) -> None:
    """Le runner, la notation et les questions ne doivent pas changer sans accord explicite :
    sinon deux scores ne mesurent plus la même chose."""
    fichier = FLUX / "harnais.sha256"
    actuelle = empreinte_harnais()
    if approuver:
        fichier.write_text(actuelle + "\n", encoding="utf-8")
        print(f"Harnais approuvé ({actuelle[:12]}…).")
        return
    if not fichier.exists() or fichier.read_text(encoding="utf-8").strip() != actuelle:
        sys.exit("Le harnais d'évaluation (runner, notation ou questions) a changé depuis la "
                 "dernière approbation. Relisez les changements puis relancez avec --approve-harness.")


def ecrire_ligne(chemin: Path, donnees: dict) -> None:
    with _ecriture, chemin.open("a", encoding="utf-8") as f:
        f.write(json.dumps(donnees, ensure_ascii=False, default=str) + "\n")


def deja_faits(dossier: Path) -> set[tuple[str, int]]:
    fichier = dossier / "results.jsonl"
    if not fichier.exists():
        return set()
    return {(r["prompt_id"], r["rep"]) for r in map(json.loads, fichier.read_text(encoding="utf-8").splitlines())}


def trace(systeme: str, cas: dict, reponse) -> list[dict]:
    tours = [{"role": "system", "content": systeme}, {"role": "user", "content": cas["question"]}]
    for a in reponse.appels:
        tours.append({"role": "tool_call", "name": a.nom,
                      "content": json.dumps(a.entree, ensure_ascii=False, indent=2)})
        tours.append({"role": "tool_result",
                      "content": json.dumps(a.resultat, ensure_ascii=False, indent=1, default=str)})
    tours.append({"role": "assistant", "content": reponse.texte})
    return tours


# --- Exécution d'un cas -------------------------------------------------------------------

def executer_cas(assistant: Assistant, juge: anthropic.Anthropic, args, cas: dict, rep: int,
                 dossier: Path) -> str:
    """Interroge l'assistant (vrai point d'entrée), note la réponse, écrit le résultat."""
    attendu = assistant.settings.claude_model
    for tentative in range(1, TENTATIVES_MAX + 1):
        conversation = assistant.nouvelle_conversation(cle_client=f"eval-{cas['id']}-{rep}-{tentative}")
        debut = time.perf_counter()
        try:
            reponse = conversation.envoyer(cas["question"])
            break
        except ERREURS_TRANSITOIRES as exc:
            if tentative == TENTATIVES_MAX:
                ecrire_ligne(dossier / "errors.jsonl", {
                    "prompt_id": cas["id"], "rep": rep, "classe": "erreur_api",
                    "detail": f"{type(exc).__name__}: {exc}", "tentatives": tentative})
                return "erreur"
            time.sleep(min(60, 2 ** tentative) * random.uniform(0.5, 1.5))  # délai aléatoire
    latence = time.perf_counter() - debut

    if reponse.modele and not reponse.modele.startswith(attendu):
        ecrire_ligne(dossier / "errors.jsonl", {
            "prompt_id": cas["id"], "rep": rep, "classe": "modele_substitue",
            "detail": f"demandé {attendu}, servi {reponse.modele}", "model": reponse.modele,
            "usage": reponse.usage, "tentatives": tentative})
        return "erreur"

    notes_auto, applicable, expl_auto = notes_automatiques(cas, reponse)
    try:
        verdict, usage_juge = juger(juge, args.juge, cas, reponse.texte, contexte_outils(reponse),
                                    assistant.settings.date_reference.isoformat(timespec="minutes"),
                                    assistant.systeme)
    except Exception as exc:
        ecrire_ligne(dossier / "errors.jsonl", {
            "prompt_id": cas["id"], "rep": rep, "classe": "erreur_juge",
            "detail": f"{type(exc).__name__}: {exc}", "model": reponse.modele,
            "usage": reponse.usage, "tentatives": tentative})
        return "erreur"
    notes, expl_juge = noter(cas, reponse.texte, notes_auto, verdict)

    (dossier / "traces").mkdir(exist_ok=True)
    (dossier / "traces" / f"{cas['id']}_rep{rep}.json").write_text(
        json.dumps(trace(assistant.systeme, cas, reponse), ensure_ascii=False, indent=1),
        encoding="utf-8")
    ecrire_ligne(dossier / "results.jsonl", {
        "prompt_id": cas["id"],
        "prompt": cas["question"],
        "tags": [cas["categorie"], cas["type_attendu"], cas["difficulte"]],
        "rep": rep,
        "stop_reason": reponse.stop_reason,
        "status": "truncated" if reponse.stop_reason == "max_tokens" else "ok",
        "grade": notes,
        "explanation": {**{k: v for k, v in expl_auto.items() if applicable[k]}, **expl_juge},
        "model": reponse.modele,
        "usage": reponse.usage,
        "judge_model": verdict["model"],
        "judge_usage": usage_juge,
        "latency_s": round(latence, 2),
        "tool_calls": len(reponse.appels),
        "meta": {"applicable": applicable, "outils": [a.nom for a in reponse.appels],
                 "sources": reponse.sources, "alertes": reponse.alertes,
                 "tentatives": tentative, "reponse": reponse.texte,
                 "verdict_elements": verdict["elements"]},
    })
    return "ok" if notes["reussite"] else "échec"


# --- Synthèse ---------------------------------------------------------------------------

PRIX = {  # $ par million de tokens (entrée, sortie) — tarifs API Anthropic
    "claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50),
}


def cout(modele: str, usage: dict) -> float:
    entree, sortie = next((p for m, p in PRIX.items() if (modele or "").startswith(m)), (0.0, 0.0))
    return (usage.get("input_tokens", 0) * entree
            + usage.get("cache_creation_input_tokens", 0) * entree * 1.25
            + usage.get("cache_read_input_tokens", 0) * entree * 0.1
            + usage.get("output_tokens", 0) * sortie) / 1e6


def synthese(dossier: Path) -> None:
    lignes = [json.loads(l) for l in (dossier / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    ok = [l for l in lignes if l["status"] == "ok"]
    erreurs = (dossier / "errors.jsonl").read_text(encoding="utf-8").splitlines() \
        if (dossier / "errors.jsonl").exists() else []
    n = len(ok)
    print(f"\n{dossier.name} : {n} cas notés, {len(lignes) - n} tronqués, {len(erreurs)} tentatives en erreur")
    for m in METRIQUES:
        valeurs = [l["grade"][m] for l in ok if l["meta"]["applicable"].get(m, True)]
        if not valeurs:
            continue
        moyenne = sum(valeurs) / len(valeurs)
        marge = 1.96 * math.sqrt(max(moyenne * (1 - moyenne), 1e-9) / len(valeurs))
        print(f"  {m:<14} {moyenne:6.1%}  ±{marge:.0%}  (sur {len(valeurs)} cas concernés)")
    par_cat: dict[str, list] = {}
    for l in ok:
        par_cat.setdefault(l["tags"][1], []).append(int(l["grade"]["reussite"]))
    print("  Réussite par type : " + ", ".join(f"{k} {sum(v)}/{len(v)}" for k, v in sorted(par_cat.items())))
    c_app = sum(cout(l["model"], l["usage"]) for l in lignes)
    c_juge = sum(cout(l["judge_model"], l["judge_usage"]) for l in lignes)
    latences = sorted(l["latency_s"] for l in ok)
    print(f"  Latence médiane {latences[len(latences) // 2]:.1f} s (max {latences[-1]:.1f} s) ; "
          f"coût assistant {c_app:.2f} $, juge {c_juge:.2f} $")
    for l in ok:
        if not l["grade"]["reussite"]:
            raisons = [f"{m}={l['grade'][m]}" for m in METRIQUES[1:]
                       if l["grade"][m] < 1 and l["meta"]["applicable"].get(m, True)]
            print(f"  ✗ {l['prompt_id']} {l['prompt'][:60]}… [{', '.join(raisons)}]")


# --- Contrôle du juge ------------------------------------------------------------------

def controle_juge(juge: anthropic.Anthropic, modele: str) -> int:
    """Le juge doit accepter la réponse de référence et rejeter trois mauvaises réponses."""
    cas = {q["id"]: q for q in json.loads(QUESTIONS.read_text(encoding="utf-8"))}["Q006"]
    outils = ("### rechercher_informations\n| Belgique : domicile standard 9,90 €, gratuit dès 150 € ; "
              "point relais 5,90 €, gratuit dès 99 € ; express non disponible |")
    essais = {
        "référence": ("La livraison à domicile en Belgique coûte 9,90 € : elle n'est gratuite qu'à "
                      "partir de 150 €, donc pas pour 120 €. En point relais, c'est gratuit dès 99 €.", True),
        "vide": ("", False),
        "je ne sais pas": ("Je ne sais pas.", False),
        "hors sujet": ("Nos PC portables sont livrés avec Windows 11 Famille, sauf les Chromebooks.", False),
    }
    consigne = consigne_systeme(get_settings().date_reference)
    echecs = 0
    for nom, (texte, doit_passer) in essais.items():
        verdict, _ = juger(juge, modele, cas, texte, outils, "2026-10-30T12:00", consigne)
        couverture = sum(e["present"] for e in verdict["elements"]) / len(verdict["elements"])
        passe = couverture >= 0.75 and verdict["fidele"]
        conforme = passe == doit_passer
        echecs += not conforme
        print(f"  {'✓' if conforme else '✗'} {nom:<15} couverture {couverture:.0%}, "
              f"fidèle={verdict['fidele']} → {'accepté' if passe else 'rejeté'}")
    return 1 if echecs else 0


# --- Renotation -----------------------------------------------------------------------------

def reponse_depuis_trace(ligne: dict, dossier: Path) -> Reponse:
    """Reconstruit la réponse enregistrée (texte, outils et résultats) sans réinterroger l'assistant."""
    tours = json.loads((dossier / "traces" / f"{ligne['prompt_id']}_rep{ligne['rep']}.json")
                       .read_text(encoding="utf-8"))
    appels = []
    for appel, resultat in zip([t for t in tours if t["role"] == "tool_call"],
                               [t for t in tours if t["role"] == "tool_result"]):
        contenu = json.loads(resultat["content"])
        appels.append(AppelOutil(appel["name"], json.loads(appel["content"]), contenu, "erreur" in contenu))
    return Reponse(texte=ligne["meta"]["reponse"], sources=ligne["meta"]["sources"], appels=appels,
                   stop_reason=ligne["stop_reason"], usage=ligne["usage"], modele=ligne["model"])


def renoter(dossier: Path, juge: anthropic.Anthropic, args) -> None:
    """Renote les réponses déjà obtenues avec le harnais actuel (ancien fichier conservé)."""
    fichier = dossier / "results.jsonl"
    anciennes = [json.loads(l) for l in fichier.read_text(encoding="utf-8").splitlines()]
    sauvegarde = dossier / f"results.avant_renotation_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
    fichier.rename(sauvegarde)
    cas_par_id = {c["id"]: c for c in charger_cas(None)}
    settings = get_settings()
    consigne = consigne_systeme(settings.date_reference)

    def traiter(ligne: dict) -> str:
        cas = cas_par_id[ligne["prompt_id"]]
        reponse = reponse_depuis_trace(ligne, dossier)
        notes_auto, applicable, expl_auto = notes_automatiques(cas, reponse)
        verdict, usage_juge = juger(juge, args.juge, cas, reponse.texte, contexte_outils(reponse),
                                    settings.date_reference.isoformat(timespec="minutes"), consigne)
        notes, expl_juge = noter(cas, reponse.texte, notes_auto, verdict)
        ecrire_ligne(fichier, {
            **ligne, "grade": notes,
            "explanation": {**{k: v for k, v in expl_auto.items() if applicable[k]}, **expl_juge},
            "judge_model": verdict["model"], "judge_usage": usage_juge,
            "meta": {**ligne["meta"], "applicable": applicable, "verdict_elements": verdict["elements"]},
        })
        changement = "" if notes["reussite"] == ligne["grade"]["reussite"] else \
            f" (avant : {'ok' if ligne['grade']['reussite'] else 'échec'})"
        return ("ok" if notes["reussite"] else "échec") + changement

    with ThreadPoolExecutor(args.concurrence) as pool:
        for ligne, statut in zip(anciennes, pool.map(traiter, anciennes)):
            print(f"  {ligne['prompt_id']} : {statut}")
    print(f"Anciennes notes conservées dans {sauvegarde.name}")


# --- Point d'entrée -------------------------------------------------------------------------

def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Évaluation de NovaTech Assist")
    p.add_argument("--variant", default="baseline", help="« baseline » ou v1, v2…")
    p.add_argument("--model", help="modèle de l'assistant (défaut : CLAUDE_MODEL du .env)")
    p.add_argument("--juge", default="claude-opus-5-5")
    p.add_argument("--reps", type=int, default=1)
    p.add_argument("--limit", type=int, help="ne traiter que les N premières questions (pilote)")
    p.add_argument("--concurrence", type=int, default=4)
    p.add_argument("--timeout-s", type=float, default=240, help="plafond de temps par cas")
    p.add_argument("--approve-harness", action="store_true")
    p.add_argument("--controle-juge", action="store_true")
    p.add_argument("--synthese", action="store_true", help="affiche la synthèse sans rien relancer")
    p.add_argument("--renoter", action="store_true",
                   help="renote les réponses déjà obtenues (après un changement de notation)")
    args = p.parse_args()

    FLUX.mkdir(parents=True, exist_ok=True)
    dossier = FLUX / args.variant
    if args.synthese:
        synthese(dossier)
        return 0
    verifier_harnais(args.approve_harness)
    juge = anthropic.Anthropic()
    if args.controle_juge:
        return controle_juge(juge, args.juge)
    if args.renoter:
        renoter(dossier, juge, args)
        synthese(dossier)
        return 0

    settings = get_settings()
    if args.model:
        settings = dataclasses.replace(settings, claude_model=args.model)
    assistant = Assistant(settings, journaliser=False)
    # Chargé avant le chronomètre : sinon la 1re question paie le chargement du modèle.
    assistant.recherche.embedder.model
    dossier.mkdir(exist_ok=True)
    faits = deja_faits(dossier)
    taches = [(c, r) for r in range(args.reps) for c in charger_cas(args.limit)
              if (c["id"], r) not in faits]
    print(f"{len(taches)} cas à exécuter sur {settings.claude_model} "
          f"(juge {args.juge}, {len(faits)} déjà faits) → {dossier}")
    print(f"  (betas : {', '.join(BETAS)})")

    debut = time.perf_counter()
    with ThreadPoolExecutor(args.concurrence) as pool:
        futurs = {pool.submit(executer_cas, assistant, juge, args, c, r, dossier): (c, r) for c, r in taches}
        for futur, (c, r) in futurs.items():
            try:
                statut = futur.result(timeout=args.timeout_s)
            except DelaiDepasse:
                ecrire_ligne(dossier / "errors.jsonl", {"prompt_id": c["id"], "rep": r,
                                                         "classe": "delai_depasse", "tentatives": 1})
                statut = "délai dépassé"
            print(f"  {c['id']} (passage {r}) : {statut}")
    print(f"Durée : {time.perf_counter() - debut:.0f} s")
    synthese(dossier)
    assistant.recherche.fermer()
    return 0


if __name__ == "__main__":
    sys.exit(main())
