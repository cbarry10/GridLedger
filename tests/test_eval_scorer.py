# tests/test_eval_scorer.py
#
# Unit tests for gridledger/analytics/eval_scorer.py
# Focus on the tolerance-based numeric_fidelity replacement.

import pytest
from gridledger.analytics.eval_scorer import (
    score_memo,
    _numeric_fidelity,
    _extract_numbers_from_memo,
    _value_present_in_memo,
    _section_coverage,
    _length_compliance,
    _hedge_present,
    _has_recommendation,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _clean_fcf(
    revenue=15_200_000_000,
    net_income=2_100_000_000,
    ocf=4_100_000_000,
    capex=3_800_000_000,
    fcf=300_000_000,
    fcf_margin=0.0197,
):
    return {
        "revenue": revenue,
        "net_income": net_income,
        "operating_cash_flow": ocf,
        "capex": capex,
        "fcf": fcf,
        "fcf_margin": fcf_margin,
        "errors": [],
    }


FULL_MEMO = """\
## 1. Business Overview
Dominion Energy operates as a regulated electric and natural gas utility serving customers
across the southeastern United States.

## 2. Financial Performance
Revenue of $15.2B with operating cash flow of $4.1B and capital expenditures of $3.8B.
Free cash flow stands at $0.3B with an FCF margin of 1.97%.

## 3. Capital Allocation
CapEx represents 92.7% of operating cash flow, indicating high reinvestment intensity.
The company may face constraints on shareholder returns.

## 4. Key Risks
Regulatory risk, rising interest rates, and capital intensity limit financial flexibility.
Subject to rate case approvals that could affect future cash flows.

## 5. Investment Signal
Cautious — low FCF margin warrants monitoring of capital allocation strategy.
"""


# ---------------------------------------------------------------------------
# _extract_numbers_from_memo
# ---------------------------------------------------------------------------

class TestExtractNumbers:
    def test_extracts_billions(self):
        numbers = _extract_numbers_from_memo("Revenue was $15.2B last year")
        assert any(abs(n - 15_200_000_000) / 15_200_000_000 < 0.01 for n in numbers)

    def test_extracts_billions_word(self):
        numbers = _extract_numbers_from_memo("Revenue of $15.2 billion")
        assert any(abs(n - 15_200_000_000) / 15_200_000_000 < 0.01 for n in numbers)

    def test_extracts_millions(self):
        numbers = _extract_numbers_from_memo("FCF of $300M")
        assert any(abs(n - 300_000_000) / 300_000_000 < 0.01 for n in numbers)

    def test_extracts_plain_large_number(self):
        numbers = _extract_numbers_from_memo("The value is 15200000000")
        assert 15_200_000_000.0 in numbers

    def test_empty_memo_returns_empty_list(self):
        assert _extract_numbers_from_memo("") == []

    def test_memo_with_no_numbers(self):
        assert _extract_numbers_from_memo("Revenue looks strong this quarter.") == []


# ---------------------------------------------------------------------------
# _value_present_in_memo
# ---------------------------------------------------------------------------

class TestValuePresentInMemo:
    def test_exact_billion_match(self):
        numbers = [15_200_000_000.0]
        assert _value_present_in_memo(15_200_000_000, numbers) is True

    def test_within_one_percent_tolerance(self):
        numbers = [15_150_000_000.0]  # ~0.3% off
        assert _value_present_in_memo(15_200_000_000, numbers) is True

    def test_outside_one_percent_fails(self):
        numbers = [14_000_000_000.0]  # ~8% off — too far
        assert _value_present_in_memo(15_200_000_000, numbers) is False

    def test_empty_memo_numbers(self):
        assert _value_present_in_memo(15_200_000_000, []) is False


# ---------------------------------------------------------------------------
# _numeric_fidelity (integration)
# ---------------------------------------------------------------------------

class TestNumericFidelity:
    def test_full_memo_high_fidelity(self):
        score = _numeric_fidelity(FULL_MEMO, _clean_fcf())
        assert score >= 0.6, f"Expected ≥0.6, got {score}"

    def test_empty_memo_zero_fidelity(self):
        score = _numeric_fidelity("", _clean_fcf())
        assert score == 0.0

    def test_no_source_values_returns_one(self):
        empty_fcf = {k: None for k in ["revenue", "net_income", "operating_cash_flow",
                                        "capex", "fcf", "fcf_margin"]}
        score = _numeric_fidelity(FULL_MEMO, empty_fcf)
        assert score == 1.0

    def test_memo_with_correct_billions_format(self):
        memo = "Revenue: $15.2B, OCF: $4.1B, CapEx: $3.8B, FCF: $0.3B"
        score = _numeric_fidelity(memo, _clean_fcf())
        assert score >= 0.6

    def test_verbatim_raw_numbers_also_work(self):
        # Raw integer strings should still match via plain-number extractor
        memo = "15200000000 in revenue and 4100000000 in operating cash flow"
        score = _numeric_fidelity(memo, _clean_fcf())
        assert score >= 0.4


# ---------------------------------------------------------------------------
# _section_coverage
# ---------------------------------------------------------------------------

class TestSectionCoverage:
    def test_full_memo_has_all_sections(self):
        score = _section_coverage(FULL_MEMO)
        assert score == 1.0

    def test_missing_section_reduces_score(self):
        partial = FULL_MEMO.replace("## 4. Key Risks", "## 4. Concerns")
        score = _section_coverage(partial)
        assert score < 1.0

    def test_empty_memo_zero_coverage(self):
        assert _section_coverage("") == 0.0


# ---------------------------------------------------------------------------
# _length_compliance
# ---------------------------------------------------------------------------

class TestLengthCompliance:
    def test_short_memo_compliant(self):
        short = "This is a short memo. " * 10  # ~40 words
        assert _length_compliance(short) == 1.0

    def test_long_memo_noncompliant(self):
        long_memo = "word " * 500
        assert _length_compliance(long_memo) == 0.0

    def test_exactly_400_words_compliant(self):
        memo = "word " * 400
        assert _length_compliance(memo) == 1.0


# ---------------------------------------------------------------------------
# score_memo (composite)
# ---------------------------------------------------------------------------

class TestScoreMemo:
    def test_returns_all_required_keys(self):
        scores = score_memo(FULL_MEMO, _clean_fcf())
        assert "composite_score" in scores
        assert "numeric_fidelity" in scores
        assert "section_coverage" in scores
        assert "length_compliance" in scores
        assert "has_recommendation" in scores
        assert "hedge_present" in scores
        assert "word_count" in scores

    def test_composite_between_zero_and_one(self):
        scores = score_memo(FULL_MEMO, _clean_fcf())
        assert 0.0 <= scores["composite_score"] <= 1.0

    def test_word_count_correct(self):
        scores = score_memo(FULL_MEMO, _clean_fcf())
        expected_wc = len(FULL_MEMO.split())
        assert scores["word_count"] == expected_wc

    def test_full_memo_composite_above_threshold(self):
        scores = score_memo(FULL_MEMO, _clean_fcf())
        assert scores["composite_score"] >= 0.5, f"Composite {scores['composite_score']} too low"

    def test_accepts_optional_unused_third_arg(self):
        # Backwards compatibility: old callers pass a revenue dict as 3rd arg
        scores = score_memo(FULL_MEMO, _clean_fcf(), {"legacy": "dict"})
        assert "composite_score" in scores

    def test_empty_memo_low_score(self):
        scores = score_memo("", _clean_fcf())
        assert scores["composite_score"] < 0.5
