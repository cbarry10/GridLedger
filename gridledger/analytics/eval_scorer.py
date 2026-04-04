# gridledger/analytics/eval_scorer.py
#
# Cortex v3 — Updated for SEC financial domain
#
# Layer 1: Rule-based eval metrics (deterministic, free, always run).
# Layer 2: LLM-as-judge (optional, triggered by GRIDLEDGER_LLM_EVAL=1).
#
# Key change from CAISO version:
#   _numeric_fidelity() previously did verbatim string check (e.g. "15200000000").
#   Financial values appear as "$15.2B" or "$15.2 billion" — verbatim fails.
#   Replaced with tolerance-based check: parse numbers from memo text, compare
#   within 1% of source values.

import os
import re

# ---------------------------------------------------------------------------
# Layer 1: Rule-based metrics
# ---------------------------------------------------------------------------

_HEDGE_KEYWORDS = [
    "based on", "subject to", "may", "could", "suggests", "indicates",
    "appears", "uncertainty", "risk", "depending on", "should note",
]

_RECOMMENDATION_KEYWORDS = [
    "recommend", "warrants", "merits", "supports", "caution",
    "attractive", "consider", "compelling", "positive", "cautious",
    "negative", "favorable", "unfavorable", "avoid", "proceed",
    "investment signal",
]

_SECTION_HEADERS = [
    "business overview",
    "financial performance",
    "capital allocation",
    "key risks",
    "investment signal",
]

_NUMERIC_TOLERANCE = 0.01   # 1% variance tolerance for numeric fidelity


def _word_count(text: str) -> int:
    return len(text.split())


def _length_compliance(memo: str) -> float:
    """Senior Banker memo target: under 400 words."""
    return 1.0 if _word_count(memo) <= 400 else 0.0


def _section_coverage(memo: str) -> float:
    """Check that all 5 required sections are present."""
    memo_lower = memo.lower()
    hits = sum(1 for header in _SECTION_HEADERS if header in memo_lower)
    return round(hits / len(_SECTION_HEADERS), 3)


def _numeric_fidelity(memo: str, fcf_output: dict, _unused: dict | None = None) -> float:
    """
    Tolerance-based numeric fidelity check.

    Extracts all numbers from the memo text, then checks what fraction of
    source financial values appear in the memo within 1% tolerance.

    Handles: "$15.2B", "$15.2 billion", "15,200", "1.97%", etc.
    """
    source_values = [
        fcf_output.get("revenue"),
        fcf_output.get("net_income"),
        fcf_output.get("operating_cash_flow"),
        fcf_output.get("capex"),
        fcf_output.get("fcf"),
    ]
    source_values = [v for v in source_values if v is not None]

    if not source_values:
        return 1.0

    memo_numbers = _extract_numbers_from_memo(memo)

    if not memo_numbers:
        return 0.0

    hits = 0
    for src in source_values:
        if _value_present_in_memo(src, memo_numbers):
            hits += 1

    return round(hits / len(source_values), 3)


def _extract_numbers_from_memo(memo: str) -> list[float]:
    """
    Parse numeric values from memo text in various formats:
      $15.2B, $15.2 billion, $1.97%, 15,200,000,000, 4.1B, etc.
    Returns list of float values (billions converted to raw, % as fraction).
    """
    numbers: list[float] = []

    # "$X.XB" or "$X.X billion/trillion"
    for m in re.finditer(
        r"\$?([\d,]+\.?\d*)\s*(B|billion|T|trillion|M|million)\b",
        memo,
        re.IGNORECASE,
    ):
        val_str = m.group(1).replace(",", "")
        suffix = m.group(2).lower()
        try:
            val = float(val_str)
            if suffix in ("b", "billion"):
                val *= 1_000_000_000
            elif suffix in ("t", "trillion"):
                val *= 1_000_000_000_000
            elif suffix in ("m", "million"):
                val *= 1_000_000
            numbers.append(val)
        except ValueError:
            pass

    # Percentages like "1.97%" → store as 0.0197 too? No — keep raw percent
    # for margin checks; the source values are raw dollars so won't match anyway.

    # Plain large numbers: 15,200,000,000 or 15200000000
    for m in re.finditer(r"\b([\d]{4,}(?:,[\d]{3})*)\b", memo):
        val_str = m.group(1).replace(",", "")
        try:
            numbers.append(float(val_str))
        except ValueError:
            pass

    return numbers


def _value_present_in_memo(source_val: int | float, memo_numbers: list[float]) -> bool:
    """Return True if source_val is within _NUMERIC_TOLERANCE of any memo number."""
    if source_val == 0:
        return 0.0 in memo_numbers
    for n in memo_numbers:
        if abs(n - source_val) / abs(source_val) <= _NUMERIC_TOLERANCE:
            return True
    return False


def _hedge_present(memo: str) -> float:
    memo_lower = memo.lower()
    return 1.0 if any(kw in memo_lower for kw in _HEDGE_KEYWORDS) else 0.0


def _has_recommendation(memo: str) -> float:
    memo_lower = memo.lower()
    return 1.0 if any(kw in memo_lower for kw in _RECOMMENDATION_KEYWORDS) else 0.0


def _composite(scores: dict) -> float:
    weights = {
        "numeric_fidelity":  0.30,
        "section_coverage":  0.30,
        "has_recommendation": 0.15,
        "length_compliance": 0.15,
        "hedge_present":     0.10,
    }
    total = sum(scores.get(k, 0) * w for k, w in weights.items())
    return round(total, 3)


def score_memo(memo: str, fcf_output: dict, _unused: dict | None = None) -> dict:
    """
    Returns a dict of all Layer 1 scores plus composite.

    Signature accepts an optional third argument for backwards compatibility
    with any existing callers that pass a revenue dict.
    """
    scores = {
        "length_compliance":  _length_compliance(memo),
        "section_coverage":   _section_coverage(memo),
        "numeric_fidelity":   _numeric_fidelity(memo, fcf_output),
        "hedge_present":      _hedge_present(memo),
        "has_recommendation": _has_recommendation(memo),
    }
    scores["composite_score"] = _composite(scores)
    scores["word_count"] = _word_count(memo)
    return scores


# ---------------------------------------------------------------------------
# Layer 2: LLM-as-judge (optional)
# ---------------------------------------------------------------------------

def score_memo_llm(
    memo: str,
    fcf_output: dict,
    _unused: dict | None = None,
    model: str = "claude-haiku-4-5-20251001",
) -> dict:
    """
    Optional LLM-as-judge scoring. Only called when GRIDLEDGER_LLM_EVAL=1.
    Scores on 3 axes (1–5 each):
      - analytical_depth: goes beyond restating numbers
      - investor_utility: actionable for an investment decision
      - factual_accuracy: stated facts match input data
    """
    import json as _json

    try:
        from anthropic import Anthropic
        from gridledger.config.settings import ANTHROPIC_API_KEY

        client = Anthropic(api_key=ANTHROPIC_API_KEY)

        judge_prompt = f"""You are evaluating an AI-generated investment memo for Dominion Energy.

Score the memo below on three dimensions (integer 1–5 each):
- analytical_depth: Does the memo go beyond restating numbers with genuine insight?
- investor_utility: Would an institutional investor find this useful for a real decision?
- factual_accuracy: Do the numbers and claims match the provided financial input?

Input financials:
Revenue: {fcf_output.get('revenue')}
Net Income: {fcf_output.get('net_income')}
Operating Cash Flow: {fcf_output.get('operating_cash_flow')}
CapEx: {fcf_output.get('capex')}
FCF: {fcf_output.get('fcf')}
FCF Margin: {fcf_output.get('fcf_margin')}

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

    except Exception as exc:
        return {"llm_judge_error": str(exc)}
