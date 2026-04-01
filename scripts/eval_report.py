#!/usr/bin/env python3
"""
LLM Eval Scorecard
Run: python scripts/eval_report.py

Reads outputs/eval_log.jsonl and prints a scorecard grouped by prompt version.

Metric definitions:
  numeric_fidelity    — fraction of key input numbers appearing in output
                        (primary hallucination detector for finance docs)
  risk_tone_alignment — memo tone keywords match computed risk level
  length_compliance   — output word count ≤ 200 (prompt spec)
  has_recommendation  — directional investment language present
  hedge_present       — uncertainty qualifiers present (calibration check)
  no_bullets          — no bullet points (prose-only format spec)
  composite_score     — weighted aggregate of above (numeric_fidelity 35%,
                        risk_tone 25%, length 15%, recommendation 10%,
                        hedge 10%, bullets 5%)

Optional LLM-as-judge scores (present when GRIDLEDGER_LLM_EVAL=1 was set):
  analytical_depth    — goes beyond restating numbers (1–5)
  investor_utility    — actionable for investment decisions (1–5)
  factual_accuracy    — stated facts match input data (1–5)
"""
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gridledger.analytics.eval_logger import load_eval_history

RULE_METRICS = [
    "composite_score",
    "numeric_fidelity",
    "risk_tone_alignment",
    "length_compliance",
    "has_recommendation",
    "hedge_present",
    "no_bullets",
]

LLM_METRICS = ["analytical_depth", "investor_utility", "factual_accuracy"]

HALLUCINATION_THRESHOLD = 0.5


def _mean(values):
    return sum(values) / len(values) if values else None


def _fmt(value, is_llm=False):
    if value is None:
        return "   N/A"
    if is_llm:
        return f"{value:5.2f}"
    return f"{value:5.3f}"


def print_eval_report():
    records = load_eval_history()

    if not records:
        print("No eval history found. Run `python main.py` first.")
        return

    total = len(records)

    # Group by prompt version
    by_version = defaultdict(list)
    for r in records:
        by_version[r.get("prompt_version", "unknown")].append(r)

    # Hallucination alerts
    alerts = [
        r for r in records
        if r.get("scores", {}).get("numeric_fidelity", 1.0) < HALLUCINATION_THRESHOLD
    ]

    print("\n" + "=" * 70)
    print("  GridLedger | LLM Eval Scorecard")
    print("=" * 70)
    print(f"\n  Total evaluations : {total}")
    print(f"  Prompt versions   : {len(by_version)}")

    if alerts:
        print(f"\n  ⚠  HALLUCINATION ALERTS: {len(alerts)} run(s) with numeric_fidelity < {HALLUCINATION_THRESHOLD}")
        for a in alerts:
            ts = a.get("timestamp", "")[:19].replace("T", " ")
            fid = a.get("scores", {}).get("numeric_fidelity", "?")
            pv = a.get("prompt_version", "?")
            print(f"     [{ts}] prompt={pv}  numeric_fidelity={fid}")

    # Per-version aggregate scores
    print("\n  ── Aggregate Scores by Prompt Version " + "─" * 30)
    header = f"  {'Version':<10} {'N':>4}  " + "  ".join(f"{m[:10]:>10}" for m in RULE_METRICS)
    print(header)
    print("  " + "-" * (len(header) - 2))

    for version in sorted(by_version.keys()):
        runs = by_version[version]
        n = len(runs)
        means = []
        for m in RULE_METRICS:
            vals = [r["scores"][m] for r in runs if r.get("scores") and m in r["scores"]]
            means.append(_mean(vals))
        row = f"  {version:<10} {n:>4}  " + "  ".join(f"{_fmt(v):>10}" for v in means)
        print(row)

    # LLM-as-judge section (only if data exists)
    llm_records = [r for r in records if r.get("scores", {}).get("analytical_depth")]
    if llm_records:
        print("\n  ── LLM-as-Judge Scores (claude-haiku) " + "─" * 30)
        header2 = f"  {'Version':<10} {'N':>4}  " + "  ".join(f"{m[:16]:>16}" for m in LLM_METRICS)
        print(header2)
        print("  " + "-" * (len(header2) - 2))
        by_version_llm = defaultdict(list)
        for r in llm_records:
            by_version_llm[r.get("prompt_version", "unknown")].append(r)
        for version in sorted(by_version_llm.keys()):
            runs = by_version_llm[version]
            n = len(runs)
            means = []
            for m in LLM_METRICS:
                vals = [r["scores"][m] for r in runs if r.get("scores") and m in r["scores"]]
                means.append(_mean(vals))
            row = f"  {version:<10} {n:>4}  " + "  ".join(f"{_fmt(v, is_llm=True):>16}" for v in means)
            print(row)

    # Recent runs detail table
    print("\n  ── Recent Evaluations (last 5) " + "─" * 37)
    print(f"  {'Timestamp':<20} {'Ver':<5} {'Words':>5}  {'Composite':>9}  {'Num.Fid':>7}  {'Tone':>5}  {'Rec':>4}")
    print("  " + "-" * 65)
    for r in records[-5:][::-1]:
        ts = r.get("timestamp", "")[:19].replace("T", " ")
        pv = r.get("prompt_version", "?")
        sc = r.get("scores", {})
        words = sc.get("word_count", "?")
        comp = sc.get("composite_score")
        fid = sc.get("numeric_fidelity")
        tone = sc.get("risk_tone_alignment")
        rec = sc.get("has_recommendation")
        print(
            f"  {ts:<20} {pv:<5} {str(words):>5}  "
            f"{_fmt(comp):>9}  {_fmt(fid):>7}  {_fmt(tone):>5}  {_fmt(rec):>4}"
        )

    print("\n  Metric Guide:")
    print("  • composite_score    weighted aggregate (0.0–1.0, higher = better)")
    print("  • numeric_fidelity   hallucination risk (< 0.5 triggers alert)")
    print("  • risk_tone_alignment memo tone matches computed risk level")
    print("  • length_compliance  output ≤ 200 words per prompt spec")
    print("  • has_recommendation clear directional language present")
    print("  • hedge_present      uncertainty qualifiers present")
    print("  • no_bullets         prose-only format respected")
    print("\n  To enable LLM-as-judge scoring: GRIDLEDGER_LLM_EVAL=1 python main.py")
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    print_eval_report()
