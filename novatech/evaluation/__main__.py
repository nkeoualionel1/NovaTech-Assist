"""Évaluation de l'assistant sur les 40 questions sélectionnées (phase 8).

Usage :
    python -m novatech.evaluation                          # variante « baseline », 1 passage
    python -m novatech.evaluation --limit 5                # pilote sur 5 questions
    python -m novatech.evaluation --variant v1 --model claude-opus-5-5 --reps 2
    python -m novatech.evaluation --check-judge            # vérifie que le juge rejette les mauvaises réponses
    python -m novatech.evaluation --regrade                # renote les réponses existantes (notation modifiée)

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
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from pathlib import Path

import anthropic

from ..assistant import Assistant, Reply, ToolCall
from ..assistant.agent import BETAS
from ..assistant.prompt import build_system_prompt
from ..config import ROOT, get_settings
from .grading import METRICS, automatic_grades, combine_grades, judge, tool_context

FLOW_DIR = ROOT / ".claude" / "hillclimb" / "assistant"
SELECTION_FILE = ROOT / "Dataset" / "evaluation" / "selection_40.json"
QUESTIONS_FILE = ROOT / "Dataset" / "evaluation" / "questions_test.json"
HARNESS_FILES = [Path(__file__), Path(__file__).with_name("grading.py"), SELECTION_FILE, QUESTIONS_FILE]
TRANSIENT_ERRORS = (anthropic.RateLimitError, anthropic.InternalServerError,
                    anthropic.APIConnectionError)
MAX_ATTEMPTS = 4
_write_lock = threading.Lock()


# --- Cas, harnais, fichiers -------------------------------------------------------------

def load_cases(limit: int | None) -> list[dict]:
    ids = json.loads(SELECTION_FILE.read_text(encoding="utf-8"))["ids"]
    questions = {q["id"]: q for q in json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))}
    return [questions[i] for i in ids][:limit]


def harness_fingerprint() -> str:
    # Fins de ligne normalisées : git peut les convertir sous Windows sans vraie modification.
    digest = hashlib.sha256()
    for path in sorted(HARNESS_FILES):
        digest.update(path.relative_to(ROOT).as_posix().encode() + b"\0"
                      + path.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def check_harness(approve: bool) -> None:
    """Le runner, la notation et les questions ne doivent pas changer sans accord explicite :
    sinon deux scores ne mesurent plus la même chose."""
    approval_file = FLOW_DIR / "harness.sha256"
    current = harness_fingerprint()
    if approve:
        approval_file.write_text(current + "\n", encoding="utf-8")
        print(f"Harnais approuvé ({current[:12]}…).")
        return
    if not approval_file.exists() or approval_file.read_text(encoding="utf-8").strip() != current:
        sys.exit("Le harnais d'évaluation (runner, notation ou questions) a changé depuis la "
                 "dernière approbation. Relisez les changements puis relancez avec --approve-harness.")


def append_jsonl(path: Path, record: dict) -> None:
    with _write_lock, path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def completed_keys(run_dir: Path) -> set[tuple[str, int]]:
    results_file = run_dir / "results.jsonl"
    if not results_file.exists():
        return set()
    rows = map(json.loads, results_file.read_text(encoding="utf-8").splitlines())
    return {(row["prompt_id"], row["rep"]) for row in rows}


def build_trace(system_prompt: str, case: dict, reply: Reply) -> list[dict]:
    turns = [{"role": "system", "content": system_prompt}, {"role": "user", "content": case["question"]}]
    for call in reply.tool_calls:
        turns.append({"role": "tool_call", "name": call.name,
                      "content": json.dumps(call.input, ensure_ascii=False, indent=2)})
        turns.append({"role": "tool_result",
                      "content": json.dumps(call.result, ensure_ascii=False, indent=1, default=str)})
    turns.append({"role": "assistant", "content": reply.text})
    return turns


def explanations_for(auto_explanations: dict, applicable: dict, judge_explanations: dict) -> dict:
    return {**{k: v for k, v in auto_explanations.items() if applicable[k]}, **judge_explanations}


# --- Exécution d'un cas -------------------------------------------------------------------

def run_case(assistant: Assistant, judge_client: anthropic.Anthropic, args, case: dict, rep: int,
             run_dir: Path) -> str:
    """Interroge l'assistant (vrai point d'entrée), note la réponse, écrit le résultat."""
    requested_model = assistant.settings.claude_model
    for attempt in range(1, MAX_ATTEMPTS + 1):
        conversation = assistant.new_conversation(client_key=f"eval-{case['id']}-{rep}-{attempt}")
        start = time.perf_counter()
        try:
            reply = conversation.send(case["question"])
            break
        except TRANSIENT_ERRORS as exc:
            if attempt == MAX_ATTEMPTS:
                append_jsonl(run_dir / "errors.jsonl", {
                    "prompt_id": case["id"], "rep": rep, "class": "api_error",
                    "detail": f"{type(exc).__name__}: {exc}", "attempts": attempt})
                return "erreur"
            time.sleep(min(60, 2 ** attempt) * random.uniform(0.5, 1.5))  # délai aléatoire
    latency = time.perf_counter() - start

    if reply.model and not reply.model.startswith(requested_model):
        append_jsonl(run_dir / "errors.jsonl", {
            "prompt_id": case["id"], "rep": rep, "class": "model_mismatch",
            "detail": f"demandé {requested_model}, servi {reply.model}", "model": reply.model,
            "usage": reply.usage, "attempts": attempt})
        return "erreur"

    auto_grades, applicable, auto_explanations = automatic_grades(case, reply)
    try:
        verdict, judge_usage = judge(judge_client, args.judge, case, reply.text, tool_context(reply),
                                     assistant.settings.reference_date.isoformat(timespec="minutes"),
                                     assistant.system_prompt)
    except Exception as exc:
        append_jsonl(run_dir / "errors.jsonl", {
            "prompt_id": case["id"], "rep": rep, "class": "judge_error",
            "detail": f"{type(exc).__name__}: {exc}", "model": reply.model,
            "usage": reply.usage, "attempts": attempt})
        return "erreur"
    grades, judge_explanations = combine_grades(auto_grades, verdict)

    (run_dir / "traces").mkdir(exist_ok=True)
    (run_dir / "traces" / f"{case['id']}_rep{rep}.json").write_text(
        json.dumps(build_trace(assistant.system_prompt, case, reply), ensure_ascii=False, indent=1),
        encoding="utf-8")
    append_jsonl(run_dir / "results.jsonl", {
        "prompt_id": case["id"],
        "prompt": case["question"],
        "tags": [case["categorie"], case["type_attendu"], case["difficulte"]],
        "rep": rep,
        "stop_reason": reply.stop_reason,
        "status": "truncated" if reply.stop_reason == "max_tokens" else "ok",
        "grade": grades,
        "explanation": explanations_for(auto_explanations, applicable, judge_explanations),
        "model": reply.model,
        "usage": reply.usage,
        "judge_model": verdict["model"],
        "judge_usage": judge_usage,
        "latency_s": round(latency, 2),
        "tool_calls": len(reply.tool_calls),
        "meta": {"applicable": applicable, "tools": [c.name for c in reply.tool_calls],
                 "sources": reply.sources, "alerts": reply.alerts,
                 "attempts": attempt, "answer": reply.text,
                 "verdict_items": verdict["items"]},
    })
    return "ok" if grades["success"] else "échec"


# --- Synthèse ---------------------------------------------------------------------------

PRICES = {  # $ par million de tokens (entrée, sortie) — tarifs API Anthropic
    "claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50),
}


def cost_usd(model: str, usage: dict) -> float:
    input_price, output_price = next(
        (p for m, p in PRICES.items() if (model or "").startswith(m)), (0.0, 0.0))
    return (usage.get("input_tokens", 0) * input_price
            + usage.get("cache_creation_input_tokens", 0) * input_price * 1.25
            + usage.get("cache_read_input_tokens", 0) * input_price * 0.1
            + usage.get("output_tokens", 0) * output_price) / 1e6


def print_summary(run_dir: Path) -> None:
    rows = [json.loads(line) for line in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    graded = [r for r in rows if r["status"] == "ok"]
    errors_file = run_dir / "errors.jsonl"
    errors = errors_file.read_text(encoding="utf-8").splitlines() if errors_file.exists() else []
    n = len(graded)
    print(f"\n{run_dir.name} : {n} cas notés, {len(rows) - n} tronqués, {len(errors)} tentatives en erreur")
    for metric in METRICS:
        values = [r["grade"][metric] for r in graded if r["meta"]["applicable"].get(metric, True)]
        if not values:
            continue
        mean = sum(values) / len(values)
        margin = 1.96 * math.sqrt(max(mean * (1 - mean), 1e-9) / len(values))
        print(f"  {metric:<14} {mean:6.1%}  ±{margin:.0%}  (sur {len(values)} cas concernés)")
    by_type: dict[str, list] = {}
    for r in graded:
        by_type.setdefault(r["tags"][1], []).append(int(r["grade"]["success"]))
    print("  Réussite par type : " + ", ".join(f"{k} {sum(v)}/{len(v)}" for k, v in sorted(by_type.items())))
    assistant_cost = sum(cost_usd(r["model"], r["usage"]) for r in rows)
    judge_cost = sum(cost_usd(r["judge_model"], r["judge_usage"]) for r in rows)
    latencies = sorted(r["latency_s"] for r in graded)
    print(f"  Latence médiane {latencies[len(latencies) // 2]:.1f} s (max {latencies[-1]:.1f} s) ; "
          f"coût assistant {assistant_cost:.2f} $, juge {judge_cost:.2f} $")
    for r in graded:
        if not r["grade"]["success"]:
            reasons = [f"{m}={r['grade'][m]}" for m in METRICS[1:]
                       if r["grade"][m] < 1 and r["meta"]["applicable"].get(m, True)]
            print(f"  ✗ {r['prompt_id']} {r['prompt'][:60]}… [{', '.join(reasons)}]")


# --- Contrôle du juge ------------------------------------------------------------------

def check_judge(judge_client: anthropic.Anthropic, model: str) -> int:
    """Le juge doit accepter la réponse de référence et rejeter trois mauvaises réponses."""
    case = {q["id"]: q for q in json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))}["Q006"]
    tool_results = ("### search_knowledge_base\n| Belgique : domicile standard 9,90 €, gratuit dès 150 € ; "
                    "point relais 5,90 €, gratuit dès 99 € ; express non disponible |")
    trials = {
        "référence": ("La livraison à domicile en Belgique coûte 9,90 € : elle n'est gratuite qu'à "
                      "partir de 150 €, donc pas pour 120 €. En point relais, c'est gratuit dès 99 €.", True),
        "vide": ("", False),
        "je ne sais pas": ("Je ne sais pas.", False),
        "hors sujet": ("Nos PC portables sont livrés avec Windows 11 Famille, sauf les Chromebooks.", False),
    }
    system_prompt = build_system_prompt(get_settings().reference_date)
    failures = 0
    for name, (text, should_pass) in trials.items():
        verdict, _ = judge(judge_client, model, case, text, tool_results, "2026-10-30T12:00", system_prompt)
        coverage = sum(item["present"] for item in verdict["items"]) / len(verdict["items"])
        passed = coverage >= 0.75 and verdict["faithful"]
        as_expected = passed == should_pass
        failures += not as_expected
        print(f"  {'✓' if as_expected else '✗'} {name:<15} couverture {coverage:.0%}, "
              f"fidèle={verdict['faithful']} → {'accepté' if passed else 'rejeté'}")
    return 1 if failures else 0


# --- Renotation -----------------------------------------------------------------------------

def reply_from_trace(row: dict, run_dir: Path) -> Reply:
    """Reconstruit la réponse enregistrée (texte, outils et résultats) sans réinterroger l'assistant."""
    turns = json.loads((run_dir / "traces" / f"{row['prompt_id']}_rep{row['rep']}.json")
                       .read_text(encoding="utf-8"))
    tool_calls = []
    for call_turn, result_turn in zip([t for t in turns if t["role"] == "tool_call"],
                                      [t for t in turns if t["role"] == "tool_result"]):
        result = json.loads(result_turn["content"])
        tool_calls.append(ToolCall(call_turn["name"], json.loads(call_turn["content"]), result,
                                   "error" in result))
    return Reply(text=row["meta"]["answer"], sources=row["meta"]["sources"], tool_calls=tool_calls,
                 stop_reason=row["stop_reason"], usage=row["usage"], model=row["model"])


def regrade(run_dir: Path, judge_client: anthropic.Anthropic, args) -> None:
    """Renote les réponses déjà obtenues avec le harnais actuel (ancien fichier conservé)."""
    results_file = run_dir / "results.jsonl"
    previous_rows = [json.loads(line) for line in results_file.read_text(encoding="utf-8").splitlines()]
    backup = run_dir / f"results.before_regrade_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
    results_file.rename(backup)
    cases_by_id = {c["id"]: c for c in load_cases(None)}
    settings = get_settings()
    system_prompt = build_system_prompt(settings.reference_date)

    def regrade_row(row: dict) -> str:
        case = cases_by_id[row["prompt_id"]]
        reply = reply_from_trace(row, run_dir)
        auto_grades, applicable, auto_explanations = automatic_grades(case, reply)
        verdict, judge_usage = judge(judge_client, args.judge, case, reply.text, tool_context(reply),
                                     settings.reference_date.isoformat(timespec="minutes"), system_prompt)
        grades, judge_explanations = combine_grades(auto_grades, verdict)
        append_jsonl(results_file, {
            **row, "grade": grades,
            "explanation": explanations_for(auto_explanations, applicable, judge_explanations),
            "judge_model": verdict["model"], "judge_usage": judge_usage,
            "meta": {**row["meta"], "applicable": applicable, "verdict_items": verdict["items"]},
        })
        change = "" if grades["success"] == row["grade"]["success"] else \
            f" (avant : {'ok' if row['grade']['success'] else 'échec'})"
        return ("ok" if grades["success"] else "échec") + change

    with ThreadPoolExecutor(args.concurrency) as pool:
        for row, status in zip(previous_rows, pool.map(regrade_row, previous_rows)):
            print(f"  {row['prompt_id']} : {status}")
    print(f"Anciennes notes conservées dans {backup.name}")


# --- Point d'entrée -------------------------------------------------------------------------

def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Évaluation de NovaTech Assist")
    parser.add_argument("--variant", default="baseline", help="« baseline » ou v1, v2…")
    parser.add_argument("--model", help="modèle de l'assistant (défaut : CLAUDE_MODEL du .env)")
    parser.add_argument("--judge", default="claude-opus-5-5")
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--limit", type=int, help="ne traiter que les N premières questions (pilote)")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout-s", type=float, default=240, help="plafond de temps par cas")
    parser.add_argument("--approve-harness", action="store_true")
    parser.add_argument("--check-judge", action="store_true")
    parser.add_argument("--summary", action="store_true", help="affiche la synthèse sans rien relancer")
    parser.add_argument("--regrade", action="store_true",
                        help="renote les réponses déjà obtenues (après un changement de notation)")
    args = parser.parse_args()

    FLOW_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = FLOW_DIR / args.variant
    if args.summary:
        print_summary(run_dir)
        return 0
    check_harness(args.approve_harness)
    judge_client = anthropic.Anthropic()
    if args.check_judge:
        return check_judge(judge_client, args.judge)
    if args.regrade:
        regrade(run_dir, judge_client, args)
        print_summary(run_dir)
        return 0

    settings = get_settings()
    if args.model:
        settings = dataclasses.replace(settings, claude_model=args.model)
    assistant = Assistant(settings, enable_audit_log=False)
    # Chargé avant le chronomètre : sinon la 1re question paie le chargement du modèle.
    assistant.retriever.embedder.model
    run_dir.mkdir(exist_ok=True)
    done = completed_keys(run_dir)
    tasks = [(c, r) for r in range(args.reps) for c in load_cases(args.limit) if (c["id"], r) not in done]
    print(f"{len(tasks)} cas à exécuter sur {settings.claude_model} "
          f"(juge {args.judge}, {len(done)} déjà faits) → {run_dir}")
    print(f"  (betas : {', '.join(BETAS)})")

    start = time.perf_counter()
    with ThreadPoolExecutor(args.concurrency) as pool:
        futures = {pool.submit(run_case, assistant, judge_client, args, c, r, run_dir): (c, r)
                   for c, r in tasks}
        for future, (case, rep) in futures.items():
            try:
                status = future.result(timeout=args.timeout_s)
            except FutureTimeout:
                append_jsonl(run_dir / "errors.jsonl", {"prompt_id": case["id"], "rep": rep,
                                                        "class": "timeout", "attempts": 1})
                status = "délai dépassé"
            print(f"  {case['id']} (passage {rep}) : {status}")
    print(f"Durée : {time.perf_counter() - start:.0f} s")
    print_summary(run_dir)
    assistant.retriever.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
