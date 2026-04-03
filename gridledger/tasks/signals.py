# gridledger/tasks/signals.py
#
# Layer 4 — System Signals
#
# Rule-based signal detection + single LLM call for next-best-action phrasing.
# Signals fire deterministically.  The LLM only phrases the NBA — it never
# decides whether a signal fires.
#
# Output schema:
# {
#   "prior_period_available": <bool>,
#   "signals": [<str>, ...],
#   "next_best_action": <str>,
#   "signal_count": <int>
# }

from __future__ import annotations

import json
import logging
from pathlib import Path

from gridledger.config.settings import (
    ANTHROPIC_API_KEY,
    CAPEX_TO_OCF_WARN_THRESHOLD,
    CLAUDE_MODEL,
    FCF_MARGIN_WARN_THRESHOLD,
)

logger = logging.getLogger(__name__)


def compute_signals(fcf_output: dict, run_dir: str | None = None) -> dict:
    """
    Fire rule-based signals from FCF output, then call LLM for NBA phrasing.

    Args:
        fcf_output:  Output of compute_fcf()
        run_dir:     If provided, write signals.json to this directory

    Returns:
        Signals dict
    """
    signals = _detect_signals(fcf_output)
    nba = _get_next_best_action(signals, fcf_output)

    result = {
        "prior_period_available": False,   # single-period MVP; extend later
        "signals": signals,
        "next_best_action": nba,
        "signal_count": len(signals),
    }

    if run_dir:
        _persist(result, Path(run_dir))

    logger.info("Signals computed: %d signal(s) fired", len(signals))
    return result


# ---------------------------------------------------------------------------
# Rule-based signal detection (fully deterministic)
# ---------------------------------------------------------------------------


def _detect_signals(fcf_output: dict) -> list[str]:
    signals: list[str] = []

    fcf_margin = fcf_output.get("fcf_margin")
    ocf = fcf_output.get("operating_cash_flow")
    capex = fcf_output.get("capex")
    net_income = fcf_output.get("net_income")
    fcf = fcf_output.get("fcf")

    # Signal 1: Low FCF margin
    if fcf_margin is not None and fcf_margin < FCF_MARGIN_WARN_THRESHOLD:
        signals.append(
            f"FCF Margin: {fcf_margin:.2%} < {FCF_MARGIN_WARN_THRESHOLD:.0%} threshold "
            f"→ capital pressure"
        )

    # Signal 2: High CapEx relative to OCF
    if ocf and capex and ocf > 0:
        ratio = capex / ocf
        if ratio > CAPEX_TO_OCF_WARN_THRESHOLD:
            signals.append(
                f"CapEx: {ratio:.1%} of operating cash flow "
                f"(threshold: {CAPEX_TO_OCF_WARN_THRESHOLD:.0%})"
            )

    # Signal 3: Negative FCF
    if fcf is not None and fcf < 0:
        signals.append(
            f"Negative FCF: ${fcf / 1_000_000_000:.1f}B — company is consuming cash"
        )

    # Signal 4: Net loss
    if net_income is not None and net_income < 0:
        signals.append(
            f"Net loss: ${net_income / 1_000_000_000:.1f}B — profitability concern"
        )

    return signals


# ---------------------------------------------------------------------------
# LLM: next-best-action phrasing only
# ---------------------------------------------------------------------------


def _get_next_best_action(signals: list[str], fcf_output: dict) -> str:
    """
    Single LLM call — only to phrase the next best action as a concise directive.
    Signals are passed as input; LLM does NOT decide whether they fire.
    """
    if not signals:
        return "No signals detected — monitor next filing for changes."

    if not ANTHROPIC_API_KEY:
        # Graceful degradation: rule-based fallback
        return _fallback_nba(signals)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        signal_text = "\n".join(f"- {s}" for s in signals)
        prompt = (
            "You are a senior investment analyst. Based on the following signals "
            "detected from Dominion Energy's latest 10-K filing, write a single "
            "concise sentence (under 20 words) describing the most important next "
            "action an analyst should take.\n\n"
            f"Signals:\n{signal_text}\n\n"
            "Next best action (one sentence, imperative):"
        )

        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=60,
            messages=[{"role": "user", "content": prompt}],
        )
        nba = message.content[0].text.strip()
        logger.info("NBA from LLM: %s", nba)
        return nba

    except Exception as exc:
        logger.warning("LLM NBA call failed (%s) — using fallback", exc)
        return _fallback_nba(signals)


def _fallback_nba(signals: list[str]) -> str:
    """Rule-based NBA when LLM is unavailable."""
    if any("capital pressure" in s for s in signals):
        return "Review capital allocation strategy and CapEx drivers."
    if any("Negative FCF" in s for s in signals):
        return "Investigate cash flow sustainability before any investment decision."
    if any("Net loss" in s for s in signals):
        return "Assess profitability recovery timeline and debt covenants."
    return "Review flagged metrics against peer utilities before taking a position."


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def _persist(signals: dict, run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "signals.json"
    out_path.write_text(json.dumps(signals, indent=2), encoding="utf-8")
    logger.info("Signals persisted to %s", out_path)
