# gridledger/tasks/memo.py
import os
from datetime import datetime

from anthropic import Anthropic

from gridledger.config.settings import ANTHROPIC_API_KEY, CLAUDE_MODEL
from gridledger.config.prompts import ACTIVE_PROMPT_VERSION, get_prompt
from gridledger.analytics.eval_scorer import score_memo, score_memo_llm
from gridledger.analytics.eval_logger import log_eval


def generate_underwriting_memo(
    metrics: dict,
    revenue: dict,
    risk_level: str,
    start_date: str,
    end_date: str,
    run_id: str = None,
) -> str:
    """
    AC5 — Generates an underwriting-style memo using Claude.

    Uses the active versioned prompt from gridledger/config/prompts.py.
    Scores the output and logs to outputs/eval_log.jsonl.
    """
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set in environment.")

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt_version = ACTIVE_PROMPT_VERSION

    prompt = get_prompt(
        prompt_version,
        average_price=metrics["average_price"],
        min_price=metrics["min_price"],
        max_price=metrics["max_price"],
        price_range=metrics["price_range"],
        volatility=metrics["volatility"],
        observations=metrics["observations"],
        scenario=revenue["scenario"],
        battery_size_mwh=revenue["battery_size_mwh"],
        efficiency=revenue["efficiency"],
        cycles_per_day=revenue["cycles_per_day"],
        simple_revenue_estimate=revenue["simple_revenue_estimate"],
        arbitrage_proxy_revenue=revenue["arbitrage_proxy_revenue"],
        risk_level=risk_level,
        start_date=start_date,
        end_date=end_date,
    )

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    memo_text = response.content[0].text.strip()
    token_usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }

    # Layer 1: rule-based scoring (always runs)
    scores = score_memo(memo_text, metrics, revenue)

    # Layer 2: LLM-as-judge (only when GRIDLEDGER_LLM_EVAL=1)
    if os.getenv("GRIDLEDGER_LLM_EVAL") == "1":
        llm_scores = score_memo_llm(memo_text, metrics, revenue)
        scores.update(llm_scores)

    log_eval({
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "prompt_version": prompt_version,
        "model": CLAUDE_MODEL,
        "token_usage": token_usage,
        "input_metrics": metrics,
        "input_revenue": revenue,
        "raw_output": memo_text,
        "scores": scores,
    })

    return memo_text
