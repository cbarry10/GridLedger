# tests/test_fcf.py
#
# Unit tests for gridledger/tasks/fcf.py
# Covers all 25+ gaps identified in the plan-eng-review test plan.

import pytest
from gridledger.tasks.fcf import compute_fcf


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_xbrl(
    revenue=15_200_000_000,
    net_income=2_100_000_000,
    ocf=4_100_000_000,
    capex=3_800_000_000,
    period="2024-12-31",
):
    """Build a minimal xbrl_facts dict for testing."""
    def _entry(v):
        return {"value": v, "tag": "test_tag", "period": period}

    facts = {}
    if revenue is not None:
        facts["revenue"] = _entry(revenue)
    else:
        facts["revenue"] = {"value": None, "error": "no revenue data"}

    if net_income is not None:
        facts["net_income"] = _entry(net_income)
    else:
        facts["net_income"] = {"value": None, "error": "no net_income data"}

    if ocf is not None:
        facts["operating_cash_flow"] = _entry(ocf)
    else:
        facts["operating_cash_flow"] = {"value": None, "error": "no ocf data"}

    if capex is not None:
        facts["capex"] = _entry(capex)
    else:
        facts["capex"] = {"value": None, "error": "no capex data"}

    return facts


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestFCFHappyPath:
    def test_basic_fcf_computed(self):
        result = compute_fcf(_make_xbrl())
        assert result["fcf"] == 4_100_000_000 - 3_800_000_000
        assert result["fcf"] == 300_000_000

    def test_fcf_margin_computed(self):
        result = compute_fcf(_make_xbrl())
        expected_margin = 300_000_000 / 15_200_000_000
        assert abs(result["fcf_margin"] - expected_margin) < 1e-10

    def test_all_values_present(self):
        result = compute_fcf(_make_xbrl())
        assert result["revenue"] == 15_200_000_000
        assert result["net_income"] == 2_100_000_000
        assert result["operating_cash_flow"] == 4_100_000_000
        assert result["capex"] == 3_800_000_000

    def test_no_errors_on_clean_input(self):
        result = compute_fcf(_make_xbrl())
        assert result["errors"] == []

    def test_reporting_period_extracted(self):
        result = compute_fcf(_make_xbrl(period="2024-12-31"))
        assert result["reporting_period"] == "2024-12-31"

    def test_negative_fcf(self):
        # CapEx > OCF → negative FCF
        result = compute_fcf(_make_xbrl(ocf=2_000_000_000, capex=3_000_000_000))
        assert result["fcf"] == -1_000_000_000
        assert result["fcf_margin"] < 0

    def test_zero_capex(self):
        result = compute_fcf(_make_xbrl(capex=0))
        assert result["fcf"] == 4_100_000_000  # OCF - 0 = OCF

    def test_high_fcf_margin(self):
        result = compute_fcf(_make_xbrl(ocf=10_000_000_000, capex=1_000_000_000,
                                         revenue=10_000_000_000))
        assert result["fcf_margin"] == pytest.approx(0.9, rel=1e-6)


# ---------------------------------------------------------------------------
# None-safety
# ---------------------------------------------------------------------------

class TestFCFNoneSafety:
    def test_missing_ocf_returns_none_fcf(self):
        result = compute_fcf(_make_xbrl(ocf=None))
        assert result["fcf"] is None
        assert result["fcf_margin"] is None
        assert any("operating_cash_flow" in e for e in result["errors"])

    def test_missing_capex_returns_none_fcf(self):
        result = compute_fcf(_make_xbrl(capex=None))
        assert result["fcf"] is None
        assert any("capex" in e for e in result["errors"])

    def test_missing_both_ocf_capex(self):
        result = compute_fcf(_make_xbrl(ocf=None, capex=None))
        assert result["fcf"] is None
        assert any("operating_cash_flow" in e or "capex" in e for e in result["errors"])

    def test_missing_revenue_returns_none_margin(self):
        result = compute_fcf(_make_xbrl(revenue=None))
        assert result["fcf_margin"] is None
        assert any("revenue" in e for e in result["errors"])

    def test_zero_revenue_returns_none_margin(self):
        result = compute_fcf(_make_xbrl(revenue=0))
        assert result["fcf_margin"] is None
        assert any("zero" in e.lower() for e in result["errors"])

    def test_missing_net_income_not_fatal(self):
        result = compute_fcf(_make_xbrl(net_income=None))
        # FCF should still compute if only net_income is missing
        assert result["fcf"] == 300_000_000
        assert result["net_income"] is None

    def test_all_none_inputs(self):
        result = compute_fcf(_make_xbrl(
            revenue=None, net_income=None, ocf=None, capex=None
        ))
        assert result["fcf"] is None
        assert result["fcf_margin"] is None
        assert len(result["errors"]) > 0

    def test_empty_xbrl_facts(self):
        result = compute_fcf({})
        assert result["fcf"] is None
        assert result["fcf_margin"] is None


# ---------------------------------------------------------------------------
# XBRL ingestion integration (unit-level: _extract_latest_annual)
# ---------------------------------------------------------------------------

class TestXBRLExtraction:
    def test_duration_guard_filters_short_periods(self):
        """Entries with duration < 350 days must be excluded."""
        from gridledger.tasks.ingestion import _extract_latest_annual

        facts = {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "form": "10-K",
                                "start": "2024-01-01",
                                "end": "2024-03-31",  # 90 days — transition period
                                "val": 999_999_999,
                            },
                            {
                                "form": "10-K",
                                "start": "2023-01-01",
                                "end": "2023-12-31",  # 365 days — valid
                                "val": 15_200_000_000,
                            },
                        ]
                    }
                }
            }
        }
        result = _extract_latest_annual(facts, ["Revenues"])
        assert result["value"] == 15_200_000_000

    def test_empty_annual_list_returns_error_not_exception(self):
        """If all entries are short-period, return error dict not IndexError."""
        from gridledger.tasks.ingestion import _extract_latest_annual

        facts = {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "form": "10-K",
                                "start": "2024-01-01",
                                "end": "2024-03-31",  # 90 days only
                                "val": 1,
                            }
                        ]
                    }
                }
            }
        }
        result = _extract_latest_annual(facts, ["Revenues"])
        assert result["value"] is None
        assert "error" in result

    def test_tag_fallback_uses_second_tag(self):
        """If first tag has no data, should fall back to second tag."""
        from gridledger.tasks.ingestion import _extract_latest_annual

        facts = {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            {
                                "form": "10-K",
                                "start": "2023-01-01",
                                "end": "2023-12-31",
                                "val": 14_000_000_000,
                            }
                        ]
                    }
                }
            }
        }
        result = _extract_latest_annual(facts, ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax"])
        assert result["value"] == 14_000_000_000

    def test_no_tags_found_returns_error(self):
        from gridledger.tasks.ingestion import _extract_latest_annual

        result = _extract_latest_annual({}, ["NonExistentTag"])
        assert result["value"] is None
        assert "error" in result

    def test_latest_period_selected_when_multiple(self):
        """Should return the most recent full-year entry."""
        from gridledger.tasks.ingestion import _extract_latest_annual

        facts = {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "form": "10-K",
                                "start": "2022-01-01",
                                "end": "2022-12-31",
                                "val": 10_000_000_000,
                            },
                            {
                                "form": "10-K",
                                "start": "2023-01-01",
                                "end": "2023-12-31",
                                "val": 15_200_000_000,  # newer — should win
                            },
                        ]
                    }
                }
            }
        }
        result = _extract_latest_annual(facts, ["Revenues"])
        assert result["value"] == 15_200_000_000
        assert result["period"] == "2023-12-31"
