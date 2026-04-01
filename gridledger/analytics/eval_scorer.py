# gridledger/analytics/eval_scorer.py
"""
Layer 1: Rule-based eval metrics (deterministic, free, always run).
Layer 2: LLM-as-judge (optional, triggered by GRIDLEDGER_LLM_EVAL=1).

Metric design informed by:
- Hamel Husain: unit-test style evals as the foundation for LLM QA
- Guardrails AI: structural + semantic validation layers
- RAGAS: faithfulness / numeric grounding for RAG/finance outputs
- Eugene Yan: reference-free evals preferred in production
"""
import os
import re

# ---------------------------------------------------------------------------
# Layer 1: Rule-based metrics
# ---------------------------------------------------------------------------

# Risk-level → expected tone keywords
_RISK_TONE_MAP = {
    "High":   ["caution", "elevated", "volatile", "variab", "risk", "uncertain"],
    "Medium": ["moderate", "mixed", "potential", "watch", "opport", "risk"],
    "Low":    ["stable", "consistent", "modest", "low", "limited", "steady"],
}

_HEDGE_KEYWORDS = [
    "based on", "short-term", "recent", "subject to",
    "may", "could", "suggest", "indicates", "appears",
]

_RECOMMENDATION_KEYWORDS = [
    "recommend", "warrants", "merits", "supports", "caution",
    "attractive", "consider", "compelling", "justify", "favorable",
    "unfavorable", "avoid", "proceed",
]


def _word_count(text: str) -> int:
    return len(text.split())


def _length_compliance(memo: str) -> float:
    return 1.0 if _word_count(memo) <= 200 else 0.0


def _no_bullets(memo: str) -> float:
    lines = memo.splitlines()
    for line in lines:
        if re.match(r"^\s*[•\-\*]", line):
            return 0.0
    return 1.0


def _numeric_fidelity(memo: str, metrics: dict, revenue: dict) -> float:
    """
    Primary hallucination detector: checks what fraction of key input
    numbers appear verbatim in the memo output.
    """
    key_values = [
        metrics.get("average_price"),
        metrics.get("min_price"),
        metrics.get("max_price"),
        revenue.get("simple_revenue_estimate"),
        revenue.get("arbitrage_proxy_revenue"),
    ]
    key_values = [str(abs(v)) for v in key_values if v is not None]
    if not key_values:
        return 1.0
    hits = sum(1 for v in key_values if v in memo)
    return round(hits / len(key_values), 3)


def _risk_tone_alignment(memo: str, risk_level: str) -> float:
    """Checks that memo tone keywords match the computed risk level."""
    expected = _RISK_TONE_MAP.get(risk_level, [])
    if not expected:
        return 0.5
    memo_lower = memo.lower()
    hits = sum(1 for kw in expected if kw in memo_lower)
    return round(min(hits / max(len(expected) * 0.5, 1), 1.0), 3)


def _hedge_present(memo: str) -> float:
    memo_lower = memo.lower()
    return 1.0 if any(kw in memo_lower for kw in _HEDGE_KEYWORDS) else 0.0


def _has_recommendation(memo: str) -> float:
    memo_lower = memo.lower()
    return 1.0 if any(kw in memo_lower for kw in _RECOMMENDATION_KEYWORDS) else 0.0


def _composite(scores: dict) -> float:
    weights = {
        "numeric_fidelity":    0.35,
        "risk_tone_alignment": 0.25,
        "length_compliance":   0.15,
        "has_recommendation":  0.10,
        "hedge_present":       0.10,
        "no_bullets":          0.05,
    }
    total = sum(scores.get(k, 0) * w for k, w in weights.items())
    return round(total, 3)


def score_memo(memo: str, metrics: dict, revenue: dict) -> dict:
    """
    Returns a dict of all Layer 1 scores plus composite.
    """
    risk_level = metrics.get("risk_level", "Medium")
    scores = {
        "length_compliance":   _length_compliance(memo),
        "no_bullets":          _no_bullets(memo),
        "numeric_fidelity":    _numeric_fidelity(memo, metrics, revenue),
        "risk_tone_alignment": _risk_tone_alignment(memo, risk_level),
        "hedge_present":       _hedge_present(memo),
        "has_recommendation":  _has_recommendation(memo),
    }
    scores["composite_score"] = _composite(scores)
    scores["word_count"] = _word_count(memo)
    return scores


# ---------------------------------------------------------------------------
# Layer 2: LLM-as-judge (optional)
# ---------------------------------------------------------------------------

def score_memo_llm(memo: str, metrics: dict, revenue: dict, model: str = "claude-haiku-4-5-20251001") -> dict:
    """
    Optional LLM-as-judge scoring. Only called when GRIDLEDGER_LLM_EVAL=1.
    Uses a fast/cheap model to score on 3 axes (1–5 each):
      - analytical_depth: goes beyond restating numbers
      - investor_utility: actionable for an investment decision
      - factual_accuracy: stated facts match input data
    Returns scores dict, or empty dict on failure.
    """
    import json as _json
    try:
        from anthropic import Anthropic
        from gridledger.config.settings import ANTHROPIC_API_KEY

        client = Anthropic(api_key=ANTHROPIC_API_KEY)

        judge_prompt = f"""You are evaluating an AI-generated investment memo for a battery storage asset.

Score the memo below on three dimensions (integer 1–5 each):
- analytical_depth: Does the memo go beyond restating the raw numbers with genuine insight?
- investor_utility: Would an investor find this useful for making a real decision?
- factual_accuracy: Do the numbers and claims in the memo match the provided input data?

Input data:
Average Price: ${metrics.get('average_price')}/MWh
Min/Max: ${metrics.get('min_price')} / ${metrics.get('max_price')}
Volatility: {metrics.get('volatility')}
Risk Level: {metrics.get('risk_level')}
Simple Revenue: ${revenue.get('simple_revenue_estimate')}
Arbitrage Revenue: ${revenue.get('arbitrage_proxy_revenue')}

Memo to evaluate:
{memo}

Respond with ONLY a JSON object, no explanation:
{{"analytical_depth": <1-5>, "investor_utility": <1-5>, "factual_accuracy": <1-5>}}"""

        response = client.messages.create(
            model=model,
            max_tokens=100,
            messages=[{"role": "user", "content": judge_prompt}],
        )
        raw = response.content[0].text.strip()
        llm_scores = _json.loads(raw)
        llm_scores["llm_judge_model"] = model
        return llm_scores
    except Exception as e:
        return {"llm_judge_error": str(e)}
