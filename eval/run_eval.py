"""Evaluate the helpdesk on eval/questions.json.

    python -m eval.run_eval --tag qwen3-1.7b_multi --runs 3
    python -m eval.run_eval --tag qwen3-1.7b_single --mode single
    python -m eval.run_eval --tag qwen3-8b_multi --model ollama_chat/qwen3:8b
    python -m eval.run_eval --tag qwen3-1.7b_nothink --think none
    python -m eval.run_eval --tag qwen3-1.7b_multi --runs 3 --regrade   # re-score saved answers only

Each question is asked in a fresh session. Raw results go to eval/results/<tag>.jsonl (the run
resumes from there if interrupted) and metrics to eval/results/<tag>_summary.json.

Metrics
  accuracy        in-scope answer contains every expected key fact (keyword groups) and is not a refusal
  citation        answered in-scope questions that cite the expected source document
  citation_valid  answers whose [Source: ...] tags all come from tool results (no invented citations)
  retrieval_hit   in-scope questions where a tool returned the expected source
  correct_refusal out-of-scope questions answered with "I don't know"
  false_refusal   in-scope questions wrongly refused
  logged          refusals that were written to the unanswered-questions log
  routing         multi-agent only: question reached the expected specialist
"""
from __future__ import annotations

import argparse
import asyncio
import difflib
import itertools
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

from helpdesk import config

EVAL_DIR = Path(__file__).resolve().parent
RESULTS_DIR = EVAL_DIR / "results"
CITATION = re.compile(r"\[Source:[^\]]*\]")


def keyword_hit(text: str, alternative: str) -> bool:
    if alternative.startswith("re:"):
        return re.search(alternative[3:], text, re.I) is not None
    return alternative.lower() in text.lower()


def grade(q: dict, r: dict) -> dict:
    from helpdesk.runner import is_refusal

    answer = r["answer"]
    body = CITATION.sub("", answer)
    refused = is_refusal(body)
    tool_text = json.dumps(r["tool_results"], ensure_ascii=False).lower()
    cited = CITATION.findall(answer)
    g = {"refused": refused, "logged": r["logged"],
         "citation_present": bool(cited),
         # every citation in the answer must have been produced by a tool in this turn
         "citation_valid": all(c.lower().replace("\\", "") in tool_text.replace("\\", "") for c in cited) if cited else None}
    if q["in_scope"]:
        g["correct"] = (not refused) and all(any(keyword_hit(body, a) for a in group) for group in q["keywords"])
        g["cites_expected"] = (not refused) and any(s.lower() in " ".join(cited).lower() for s in q["sources"])
        g["retrieval_hit"] = any(s.lower() in tool_text for s in q["sources"])
        g["routing_ok"] = r.get("route") == q["expected_agent"] if r["mode"] != "single" else None
    else:
        g["correct"] = refused
    return g


def similarity(a: str, b: str) -> float:
    norm = lambda t: re.sub(r"\s+", " ", re.sub(r"drafts/\S+", "", t.lower())).strip()  # drop timestamped paths
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def rate(values) -> float | None:
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 3) if values else None


def summarise(questions: list[dict], rows: list[dict], tag: str, args) -> dict:
    by_q = defaultdict(list)
    for row in rows:
        by_q[row["id"]].append(row)
    qmap = {q["id"]: q for q in questions}
    ins = [r for r in rows if qmap[r["id"]]["in_scope"]]
    oos = [r for r in rows if not qmap[r["id"]]["in_scope"]]
    answered = [r for r in ins if not r["grade"]["refused"]]
    refusals = [r for r in rows if r["grade"]["refused"]]

    per_category = {}
    for cat in sorted({q["category"] for q in questions}):
        per_category[cat] = rate(r["grade"]["correct"] for r in rows if qmap[r["id"]]["category"] == cat)

    per_question, unstable = {}, []
    for qid, rs in sorted(by_q.items()):
        outcomes = [r["grade"]["correct"] for r in rs]
        pair_sims = [similarity(a["answer"], b["answer"]) for a, b in itertools.combinations(rs, 2)]
        per_question[qid] = {"correct_runs": sum(outcomes), "runs": len(rs),
                             "mean_answer_similarity": round(statistics.mean(pair_sims), 3) if pair_sims else None,
                             "routes": sorted({str(r.get("route")) for r in rs})}
        if len(rs) > 1 and (len(set(outcomes)) > 1 or (pair_sims and min(pair_sims) < 0.6)):
            unstable.append({"id": qid, "question": qmap[qid]["question"],
                             "correct_runs": f"{sum(outcomes)}/{len(rs)}",
                             "min_answer_similarity": round(min(pair_sims), 3) if pair_sims else None,
                             "answers": [r["answer"][:300] for r in rs]})

    return {
        "tag": tag, "mode": args.mode, "model": args.model or config.LLM_MODEL, "think": config.THINK,
        "temperature": config.TEMPERATURE, "runs": args.runs, "questions": len(questions),
        "metrics": {
            "accuracy_in_scope": rate(r["grade"]["correct"] for r in ins),
            "overall_accuracy": rate(r["grade"]["correct"] for r in rows),
            "citation_expected_source": rate(r["grade"]["cites_expected"] for r in answered),
            "citation_valid": rate(r["grade"]["citation_valid"] for r in rows),
            "retrieval_hit": rate(r["grade"]["retrieval_hit"] for r in ins),
            "correct_refusal_oos": rate(r["grade"]["correct"] for r in oos),
            "false_refusal_in_scope": rate(r["grade"]["refused"] for r in ins),
            "refusals_logged": rate(r["grade"]["logged"] for r in refusals),
            "routing_accuracy": rate(r["grade"].get("routing_ok") for r in ins),
            "errors": sum(1 for r in rows if r.get("error")),
            "mean_latency_s": round(statistics.mean(r["latency_s"] for r in rows), 2),
        },
        "accuracy_by_category": per_category,
        "per_question": per_question,
        "unstable_questions": unstable,
    }


async def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tag", required=True, help="name of this configuration, used for output files")
    parser.add_argument("--mode", default="multi", choices=["multi", "multi-transfer", "single"])
    parser.add_argument("--model", default=None, help="LiteLLM model id (default: config.LLM_MODEL)")
    parser.add_argument("--think", default=None, choices=["none", "policy", "all"], help="override HELPDESK_THINK")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--ids", default="", help="comma-separated subset of question ids")
    parser.add_argument("--questions", default=str(EVAL_DIR / "questions.json"))
    parser.add_argument("--regrade", action="store_true",
                        help="re-score the saved answers of this tag against the current questions; no model calls")
    args = parser.parse_args()

    if args.think:
        config.THINK = args.think
    RESULTS_DIR.mkdir(exist_ok=True)
    artifacts = RESULTS_DIR / f"{args.tag}_artifacts"
    artifacts.mkdir(exist_ok=True)
    # keep evaluation side effects out of the real log / drafts folder
    config.UNANSWERED_LOG = artifacts / "unanswered_questions.jsonl"
    config.DRAFTS_DIR = artifacts / "drafts"

    from helpdesk.runner import HelpdeskRunner

    questions = json.loads(Path(args.questions).read_text())
    if args.ids:
        wanted = set(args.ids.split(","))
        questions = [q for q in questions if q["id"] in wanted]

    raw_path = RESULTS_DIR / f"{args.tag}.jsonl"
    rows = [json.loads(line) for line in raw_path.open()] if raw_path.exists() else []
    done = {(r["run"], r["id"]) for r in rows}

    if args.regrade:
        qmap = {q["id"]: q for q in json.loads(Path(args.questions).read_text())}
        rows = [{**r, "grade": grade(qmap[r["id"]], r)} for r in rows if r["id"] in qmap]
        raw_path.write_text("".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in rows))
        if rows:
            args.mode, args.model = rows[0]["mode"], rows[0]["model"]
        done = {(r["run"], r["id"]) for r in rows} | {(run, q["id"]) for run in range(1, args.runs + 1) for q in questions}

    bot = None if args.regrade else HelpdeskRunner(mode=args.mode, model=args.model)
    with raw_path.open("a", encoding="utf-8") as out:
        for run in range(1, args.runs + 1):
            for q in questions:
                if (run, q["id"]) in done:
                    continue
                try:
                    result = await asyncio.wait_for(bot.ask(q["question"], fresh_session=True), timeout=600)
                except asyncio.TimeoutError:
                    result = {"question": q["question"], "answer": "[error] timed out", "agents": [], "tool_calls": [],
                              "tool_results": [], "route": None, "refused": False, "logged": False,
                              "error": "timeout", "latency_s": 600.0, "mode": bot.mode, "model": bot.model}
                row = {"run": run, "id": q["id"], **result, "grade": grade(q, result)}
                rows.append(row)
                out.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
                out.flush()
                mark = "ok " if row["grade"]["correct"] else "BAD"
                print(f"[{args.tag} run {run}] {q['id']} {mark} {result['latency_s']:>6}s "
                      f"{result.get('route')}  {result['answer'][:90]!r}", flush=True)

    wanted_ids = {q["id"] for q in questions}
    rows = [r for r in rows if r["id"] in wanted_ids and r["run"] <= args.runs]
    summary = summarise(questions, rows, args.tag, args)
    (RESULTS_DIR / f"{args.tag}_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps(summary["metrics"], indent=2))
    print("accuracy by category:", summary["accuracy_by_category"])


if __name__ == "__main__":
    asyncio.run(main())
