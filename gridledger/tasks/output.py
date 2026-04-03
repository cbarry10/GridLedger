# gridledger/tasks/output.py
#
# Cortex v3 — Save structured run outputs to a dated directory.
# Produces: summary.json, world_model.json, signals.json, report.txt

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from gridledger.config.settings import (
    DOMINION_NAME,
    DOMINION_TICKER,
    OUTPUT_DIR,
)

logger = logging.getLogger(__name__)


def save_structured_outputs(
    fcf_output: dict,
    world_model: dict,
    signals_output: dict,
    memo: str,
    run_id: str | None = None,
) -> str:
    """
    Save all Cortex outputs to a timestamped run directory.

    Creates:
        outputs/<YYYY-MM-DD>/summary.json
        outputs/<YYYY-MM-DD>/world_model.json
        outputs/<YYYY-MM-DD>/signals.json
        outputs/<YYYY-MM-DD>/report.txt

    Returns:
        Path to the run directory (str)
    """
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    run_dir = OUTPUT_DIR / run_date
    run_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).isoformat()

    # -------------------------
    # summary.json (full payload)
    # -------------------------
    summary = {
        "run_id": run_id,
        "timestamp": timestamp,
        "ticker": DOMINION_TICKER,
        "company": DOMINION_NAME,
        "reporting_period": fcf_output.get("reporting_period"),
        "fcf": fcf_output,
        "world_model": world_model,
        "signals": signals_output,
        "memo": memo,
    }
    _write_json(run_dir / "summary.json", summary)

    # -------------------------
    # world_model.json (standalone, for dashboard Tab 6)
    # -------------------------
    _write_json(run_dir / "world_model.json", world_model)

    # -------------------------
    # signals.json (standalone, for dashboard Tab 7)
    # -------------------------
    _write_json(run_dir / "signals.json", signals_output)

    # -------------------------
    # report.txt (human-readable)
    # -------------------------
    report = _build_report(timestamp, fcf_output, signals_output, memo)
    (run_dir / "report.txt").write_text(report, encoding="utf-8")

    logger.info("Outputs saved to: %s", run_dir)
    print(f"\n[Cortex] Outputs saved to: {run_dir}")

    return str(run_dir)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _fmt(v: int | None) -> str:
    if v is None:
        return "N/A"
    if abs(v) >= 1_000_000_000:
        return f"${v / 1_000_000_000:.1f}B"
    return f"${v / 1_000_000:.1f}M"


def _build_report(
    timestamp: str,
    fcf_output: dict,
    signals_output: dict,
    memo: str,
) -> str:
    signals = signals_output.get("signals", [])
    signal_lines = "\n".join(f"  • {s}" for s in signals) if signals else "  (none)"
    nba = signals_output.get("next_best_action", "N/A")
    period = fcf_output.get("reporting_period", "N/A")

    return f"""
CORTEX — AI FINANCIAL INTELLIGENCE SYSTEM
Dominion Energy (D) | {period}
Generated: {timestamp}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMPUTED FINANCIALS (Junior Banker — Deterministic)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Revenue:              {_fmt(fcf_output.get('revenue'))}
  Net Income:           {_fmt(fcf_output.get('net_income'))}
  Operating Cash Flow:  {_fmt(fcf_output.get('operating_cash_flow'))}
  Capital Expenditures: {_fmt(fcf_output.get('capex'))}
  Free Cash Flow:       {_fmt(fcf_output.get('fcf'))}
  FCF Margin:           {f"{fcf_output.get('fcf_margin', 0):.2%}" if fcf_output.get('fcf_margin') is not None else "N/A"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SYSTEM SIGNALS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{signal_lines}

Next Best Action: {nba}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INVESTMENT MEMO (Senior Banker — LLM)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{memo}
"""
