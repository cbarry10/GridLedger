#!/usr/bin/env python3
"""
Usage Analytics Dashboard
Run: python scripts/usage_report.py

Reads outputs/run_log.jsonl and prints a formatted usage summary.
Demonstrates admin-facing observability for enterprise deployments.
"""
import sys
from pathlib import Path
from collections import Counter, defaultdict

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gridledger.analytics.run_logger import load_run_history


def _bar(value, max_value, width=20):
    filled = int(round(value / max_value * width)) if max_value else 0
    return "█" * filled + "░" * (width - filled)


def print_usage_report():
    records = load_run_history()

    if not records:
        print("No run history found. Run `python main.py` first.")
        return

    total = len(records)
    users = Counter(r.get("user", "unknown") for r in records)
    scenarios = Counter(r.get("scenario", "unknown") for r in records)
    risks = Counter(r.get("risk_level", "unknown") for r in records)
    prompt_versions = Counter(r.get("prompt_version", "unknown") for r in records)

    # Date range
    timestamps = sorted(r["timestamp"] for r in records if r.get("timestamp"))
    date_range = f"{timestamps[0][:10]} → {timestamps[-1][:10]}" if timestamps else "N/A"

    # Avg metrics across all runs
    avg_prices = [r["avg_price"] for r in records if r.get("avg_price") is not None]
    avg_vols = [r["volatility"] for r in records if r.get("volatility") is not None]
    avg_arb = [r["arbitrage_revenue"] for r in records if r.get("arbitrage_revenue") is not None]

    print("\n" + "=" * 60)
    print("  GridLedger | Usage Analytics Dashboard")
    print("=" * 60)

    print(f"\n  Total Runs     : {total}")
    print(f"  Unique Users   : {len(users)}")
    print(f"  Date Range     : {date_range}")

    if avg_prices:
        print(f"  Avg Price (mean): ${sum(avg_prices)/len(avg_prices):.2f}/MWh")
    if avg_vols:
        print(f"  Volatility (mean): {sum(avg_vols)/len(avg_vols):.2f}")
    if avg_arb:
        print(f"  Arbitrage Rev (mean): ${sum(avg_arb)/len(avg_arb):.2f}")

    # Per-user breakdown
    print("\n  ── Runs by User " + "─" * 43)
    max_user_count = max(users.values())
    for user, count in users.most_common():
        bar = _bar(count, max_user_count)
        print(f"  {user:<20} {bar} {count}")

    # Scenario breakdown
    print("\n  ── Runs by Scenario " + "─" * 39)
    max_sc = max(scenarios.values())
    for sc, count in scenarios.most_common():
        bar = _bar(count, max_sc)
        print(f"  {sc:<20} {bar} {count}")

    # Risk distribution
    print("\n  ── Risk Distribution " + "─" * 38)
    for risk in ["Low", "Medium", "High"]:
        count = risks.get(risk, 0)
        bar = _bar(count, total)
        print(f"  {risk:<20} {bar} {count}")

    # Prompt version distribution
    print("\n  ── Prompt Versions " + "─" * 40)
    for pv, count in prompt_versions.most_common():
        bar = _bar(count, total)
        print(f"  {pv:<20} {bar} {count}")

    # Last 5 runs
    print("\n  ── Recent Runs (last 5) " + "─" * 35)
    print(f"  {'Timestamp':<24} {'User':<14} {'Scenario':<12} {'Risk':<8} {'Arb Rev':>10}")
    print("  " + "-" * 70)
    for r in records[-5:][::-1]:
        ts = r.get("timestamp", "")[:19].replace("T", " ")
        user = r.get("user", "?")[:13]
        sc = r.get("scenario", "?")[:11]
        risk = r.get("risk_level", "?")[:7]
        arb = r.get("arbitrage_revenue")
        arb_str = f"${arb:.2f}" if arb is not None else "N/A"
        print(f"  {ts:<24} {user:<14} {sc:<12} {risk:<8} {arb_str:>10}")

    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    print_usage_report()
