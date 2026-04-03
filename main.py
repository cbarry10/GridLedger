# main.py — Cortex AI Financial Intelligence System
#
# Pipeline:
#   Layer 1: Ingestion  — XBRL facts + 10-K filing download
#   Layer 2: FCF        — deterministic computation (no LLM)
#   Layer 3: World Model — grounded fact snapshot (no LLM)
#   Layer 4: Signals    — rule-based triggers + LLM for NBA phrasing
#   Layer 5: Memo       — Senior Banker 5-section memo (LLM)
#   Layer 6: Output     — save all artifacts + log run
#
# stdout → OpenClaw → Slack (keep this contract intact)

import logging
import sys
from datetime import datetime, timezone

from gridledger.config.prompts import ACTIVE_PROMPT_VERSION
from gridledger.config.settings import DOMINION_CIK, DOMINION_NAME, DOMINION_TICKER
from gridledger.tasks.fcf import compute_fcf
from gridledger.tasks.ingestion import extract_item1_context, fetch_10k_filing, fetch_xbrl_facts
from gridledger.tasks.memo import generate_investment_memo
from gridledger.tasks.output import save_structured_outputs
from gridledger.tasks.signals import compute_signals
from gridledger.tasks.world_model import build_world_model
from gridledger.analytics.run_logger import log_run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],  # logs to stderr; stdout → Slack
)
logger = logging.getLogger("cortex")


def _fmt(v: int | None) -> str:
    if v is None:
        return "N/A"
    if abs(v) >= 1_000_000_000:
        return f"${v / 1_000_000_000:.1f}B"
    return f"${v / 1_000_000:.1f}M"


def _fmt_pct(v: float | None) -> str:
    return f"{v:.2%}" if v is not None else "N/A"


def main() -> None:
    run_id = f"cortex-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    logger.info("=== Cortex run started: %s ===", run_id)

    # ------------------------------------------------------------------
    # Layer 1: Ingestion
    # ------------------------------------------------------------------
    logger.info("Layer 1: Fetching XBRL facts from SEC EDGAR…")
    xbrl_facts = fetch_xbrl_facts(DOMINION_CIK)

    logger.info("Layer 1: Downloading 10-K filing…")
    filing_result = fetch_10k_filing()
    raw_doc_path = filing_result.get("path")

    item1_context = ""
    if raw_doc_path:
        logger.info("Layer 1: Extracting Item 1 context…")
        item1_context = extract_item1_context(raw_doc_path)
    else:
        logger.warning("Layer 1: 10-K filing unavailable (%s)", filing_result.get("error"))

    # ------------------------------------------------------------------
    # Layer 2: FCF (deterministic — no LLM)
    # ------------------------------------------------------------------
    logger.info("Layer 2: Computing FCF…")
    fcf_output = compute_fcf(xbrl_facts)

    if fcf_output["errors"]:
        logger.warning("FCF errors: %s", fcf_output["errors"])

    # ------------------------------------------------------------------
    # Layer 3: World Model (deterministic — no LLM)
    # ------------------------------------------------------------------
    logger.info("Layer 3: Building World Model…")
    world_model = build_world_model(fcf_output)

    # ------------------------------------------------------------------
    # Layer 4: Signals (deterministic rules + single LLM for NBA)
    # ------------------------------------------------------------------
    logger.info("Layer 4: Computing signals…")
    signals_output = compute_signals(fcf_output)

    # ------------------------------------------------------------------
    # Layer 5: Investment Memo (LLM — sees computed outputs only)
    # ------------------------------------------------------------------
    logger.info("Layer 5: Generating investment memo…")
    memo = generate_investment_memo(
        fcf_output=fcf_output,
        signals_output=signals_output,
        item1_context=item1_context,
        run_id=run_id,
    )

    # ------------------------------------------------------------------
    # Layer 6: Output
    # ------------------------------------------------------------------
    logger.info("Layer 6: Saving outputs…")
    run_dir = save_structured_outputs(
        fcf_output=fcf_output,
        world_model=world_model,
        signals_output=signals_output,
        memo=memo,
        run_id=run_id,
    )

    # Save world_model and signals to run dir (output.py already does this,
    # but also pass to world_model/signals persist for consistency)
    build_world_model(fcf_output, run_dir=run_dir)
    compute_signals(fcf_output, run_dir=run_dir)

    # Log run
    period = fcf_output.get("reporting_period", "N/A")
    log_run({
        "run_id": run_id,
        "ticker": DOMINION_TICKER,
        "reporting_period": period,
        "prompt_version": ACTIVE_PROMPT_VERSION,
        "output_dir": run_dir,
        "revenue": fcf_output.get("revenue"),
        "net_income": fcf_output.get("net_income"),
        "operating_cash_flow": fcf_output.get("operating_cash_flow"),
        "capex": fcf_output.get("capex"),
        "fcf": fcf_output.get("fcf"),
        "fcf_margin": fcf_output.get("fcf_margin"),
        "signal_count": signals_output.get("signal_count", 0),
        "memo_word_count": len(memo.split()),
    })

    # ------------------------------------------------------------------
    # Slack summary → stdout (OpenClaw contract)
    # ------------------------------------------------------------------
    signals = signals_output.get("signals", [])
    signal_lines = "\n".join(f"  • {s}" for s in signals) if signals else "  • No signals detected"
    nba = signals_output.get("next_best_action", "N/A")

    slack_summary = (
        f"*Cortex | {DOMINION_NAME} ({DOMINION_TICKER})*\n"
        f"Period: {period}\n\n"
        f"*Computed Financials*\n"
        f"  Revenue: {_fmt(fcf_output.get('revenue'))}  |  "
        f"OCF: {_fmt(fcf_output.get('operating_cash_flow'))}  |  "
        f"CapEx: {_fmt(fcf_output.get('capex'))}\n"
        f"  FCF: {_fmt(fcf_output.get('fcf'))}  |  "
        f"FCF Margin: {_fmt_pct(fcf_output.get('fcf_margin'))}\n\n"
        f"*System Signals ({signals_output.get('signal_count', 0)})*\n"
        f"{signal_lines}\n\n"
        f"*Next Best Action*\n  {nba}\n\n"
        f"*Investment Memo*\n{memo}"
    )

    print(slack_summary)
    logger.info("=== Cortex run complete: %s ===", run_id)


if __name__ == "__main__":
    main()
