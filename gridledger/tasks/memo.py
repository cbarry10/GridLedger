# gridledger/tasks/memo.py
#
# Layer 5 — Senior Banker (LLM Memo Generation)
#
# The LLM only sees computed outputs from the Junior Banker layer.
# It never touches raw filing numbers for extraction.

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from anthropic import Anthropic

from gridledger.config.settings import ANTHROPIC_API_KEY, CLAUDE_MODEL
from gridledger.config.prompts import ACTIVE_PROMPT_VERSION, get_prompt
from gridledger.analytics.eval_scorer import score_memo, score_memo_llm
from gridledger.analytics.eval_logger import log_eval

logger = logging.getLogger(__name__)


def generate_investment_memo(
    fcf_output: dict,
    signals_output: dict,
    item1_context: str = "",
    run_id: str | None = None,
) -> str:
    """
    Generate a 5-section investment memo using the Senior Banker prompt.

    Args:
        fcf_output:      Output of compute_fcf()
        signals_output:  Output of compute_signals()
        item1_context:   Extracted text from Item 1 of the 10-K (plain text)
        run_id:          Optional run identifier for eval logging

    Returns:
        Memo text (str)
    """
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set — returning placeholder memo")
        return _placeholder_memo(fcf_output, signals_output)

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt_version = ACTIVE_PROMPT_VERSION

    # Format numeric values for the prompt
    prompt_kwargs = _build_prompt_kwargs(fcf_output, signals_output, item1_context)

    prompt = get_prompt(prompt_version, **prompt_kwargs)

    logger.info("Calling Claude for memo generation (prompt_version=%s)", prompt_version)

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        logger.warning("Claude API call failed (%s) — returning placeholder memo", exc)
        return _placeholder_memo(fcf_output, signals_output)

    memo_text = response.content[0].text.strip()
    token_usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }

    logger.info(
        "Memo generated: %d chars, %d input tokens, %d output tokens",
        len(memo_text), token_usage["input_tokens"], token_usage["output_tokens"],
    )

    # Eval scoring
    scores = score_memo(memo_text, fcf_output)

    if os.getenv("GRIDLEDGER_LLM_EVAL") == "1":
        llm_scores = score_memo_llm(memo_text, fcf_output)
        scores.update(llm_scores)

    log_eval({
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_version": prompt_version,
        "model": CLAUDE_MODEL,
        "token_usage": token_usage,
        "input_fcf": fcf_output,
        "input_signals": signals_output,
        "raw_output": memo_text,
        "scores": scores,
    })

    return memo_text


# ---------------------------------------------------------------------------
# Prompt formatting helpers
# ---------------------------------------------------------------------------


def _build_prompt_kwargs(
    fcf_output: dict,
    signals_output: dict,
    item1_context: str,
) -> dict:
    """Format all values for prompt interpolation."""

    def _fmt_dollars(v: int | None) -> str:
        if v is None:
            return "N/A"
        if abs(v) >= 1_000_000_000:
            return f"${v / 1_000_000_000:.1f}B"
        return f"${v / 1_000_000:.1f}M"

    def _fmt_pct(v: float | None) -> str:
        return f"{v:.2%}" if v is not None else "N/A"

    signals = signals_output.get("signals", [])
    signals_text = (
        "\n".join(f"  • {s}" for s in signals)
        if signals
        else "  • No signals detected"
    )

    return {
        "reporting_period": fcf_output.get("reporting_period") or "Most Recent Annual",
        "revenue_fmt":      _fmt_dollars(fcf_output.get("revenue")),
        "net_income_fmt":   _fmt_dollars(fcf_output.get("net_income")),
        "ocf_fmt":          _fmt_dollars(fcf_output.get("operating_cash_flow")),
        "capex_fmt":        _fmt_dollars(fcf_output.get("capex")),
        "fcf_fmt":          _fmt_dollars(fcf_output.get("fcf")),
        "fcf_margin_fmt":   _fmt_pct(fcf_output.get("fcf_margin")),
        "signals_text":     signals_text,
        "item1_context":    item1_context[:3000] if item1_context else "Not available.",
    }


def _placeholder_memo(fcf_output: dict, signals_output: dict) -> str:
    """
    Returned when Claude API is unavailable.  Shows computed facts only —
    no fabricated analysis.  Clearly marked as a placeholder.
    """
    def _fmt(v):
        if v is None:
            return "N/A"
        if abs(v) >= 1_000_000_000:
            return f"${v / 1_000_000_000:.1f}B"
        return f"${v / 1_000_000:.1f}M"

    signals = signals_output.get("signals", [])
    signal_lines = "\n".join(f"- {s}" for s in signals) if signals else "- None detected"

    return (
        "## Memo Unavailable — API Key Required\n\n"
        "Set `ANTHROPIC_API_KEY` in your `.env` file to generate the investment memo.\n\n"
        "---\n\n"
        "**Computed facts are available below (no LLM required):**\n\n"
        f"- Revenue: {_fmt(fcf_output.get('revenue'))}\n"
        f"- Operating Cash Flow: {_fmt(fcf_output.get('operating_cash_flow'))}\n"
        f"- CapEx: {_fmt(fcf_output.get('capex'))}\n"
        f"- FCF: {_fmt(fcf_output.get('fcf'))}\n"
        f"- FCF Margin: {'{:.2%}'.format(fcf_output['fcf_margin']) if fcf_output.get('fcf_margin') is not None else 'N/A'}\n\n"
        f"**Active signals:**\n{signal_lines}\n\n"
        f"**Next best action:** {signals_output.get('next_best_action', 'N/A')}"
    )
