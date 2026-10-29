"""Combine every eval/results/*_summary.json into eval/results/summary.md (tables used in the report).

    python -m eval.summarize
"""
import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"

COLUMNS = [
    ("accuracy_in_scope", "Accuracy (in-scope, auto)"),
    ("accuracy_audited", "Accuracy (audited)"),
    ("citation_expected_source", "Correct citation"),
    ("citation_valid", "Citations genuine"),
    ("retrieval_hit", "Retrieval/tool hit"),
    ("correct_refusal_oos", "Correct refusal (OOS)"),
    ("false_refusal_in_scope", "False refusal"),
    ("refusals_logged", "Refusals logged"),
    ("routing_accuracy", "Routing acc."),
    ("mean_latency_s", "Latency (s)"),
]


def fmt(v, key):
    if v is None:
        return "-"
    return f"{v:.2f}" if key == "mean_latency_s" else f"{100 * v:.0f}%"


def audited_accuracy(tag: str) -> float | None:
    """Re-score in-scope answers with the manual overrides from eval/manual_audit.json."""
    raw = RESULTS / f"{tag}.jsonl"
    if not raw.exists():
        return None
    audit = json.loads((RESULTS.parent / "manual_audit.json").read_text())["overrides"]
    overrides = {(o["run"], o["id"]): o["correct"] for o in audit if o["tag"] == tag}
    rows = [json.loads(line) for line in raw.open()]
    scored = [overrides.get((r["run"], r["id"]), r["grade"]["correct"]) for r in rows if "routing_ok" in r["grade"]]
    return sum(scored) / len(scored) if scored else None


def main():
    summaries = [json.loads(p.read_text()) for p in sorted(RESULTS.glob("*_summary.json"))]
    for s in summaries:
        s["metrics"]["accuracy_audited"] = audited_accuracy(s["tag"])
    lines = ["# Evaluation summary", "",
             "| Configuration | Model | Mode | Think | Runs | " + " | ".join(c[1] for c in COLUMNS) + " |",
             "|" + "---|" * (5 + len(COLUMNS))]
    for s in summaries:
        m = s["metrics"]
        lines.append(f"| {s['tag']} | {s['model'].split('/')[-1]} | {s['mode']} | {s['think']} | {s['runs']} | "
                     + " | ".join(fmt(m.get(k), k) for k, _ in COLUMNS) + " |")

    cats = sorted({c for s in summaries for c in s["accuracy_by_category"]})
    lines += ["", "## Accuracy by category", "", "| Configuration | " + " | ".join(cats) + " |",
              "|" + "---|" * (1 + len(cats))]
    for s in summaries:
        lines.append(f"| {s['tag']} | " + " | ".join(fmt(s["accuracy_by_category"].get(c), c) for c in cats) + " |")

    ids = sorted({q for s in summaries for q in s["per_question"]})
    lines += ["", "## Per-question correct runs", "", "| Question | " + " | ".join(s["tag"] for s in summaries) + " |",
              "|" + "---|" * (1 + len(summaries))]
    for qid in ids:
        cells = []
        for s in summaries:
            pq = s["per_question"].get(qid)
            cells.append(f"{pq['correct_runs']}/{pq['runs']}" if pq else "-")
        lines.append(f"| {qid} | " + " | ".join(cells) + " |")

    lines += ["", "## Questions whose answers changed across runs", ""]
    for s in summaries:
        if s["runs"] < 2:
            continue
        lines.append(f"### {s['tag']}")
        if not s["unstable_questions"]:
            lines.append("No question changed outcome across runs.")
        for u in s["unstable_questions"]:
            lines.append(f"- **{u['id']}** {u['question']} - correct in {u['correct_runs']} runs, "
                         f"min. pairwise answer similarity {u['min_answer_similarity']}")
        lines.append("")
    (RESULTS / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
