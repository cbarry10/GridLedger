# tests/test_world_model.py
#
# Unit tests for gridledger/tasks/world_model.py

import json
import pytest
from pathlib import Path
from gridledger.tasks.world_model import build_world_model, _derive_understanding


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
    period="2024-12-31",
    errors=None,
):
    return {
        "revenue": revenue,
        "net_income": net_income,
        "operating_cash_flow": ocf,
        "capex": capex,
        "fcf": fcf,
        "fcf_margin": fcf_margin,
        "reporting_period": period,
        "errors": errors or [],
    }


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestWorldModelSchema:
    def test_output_has_required_keys(self):
        wm = build_world_model(_clean_fcf())
        assert "meta" in wm
        assert "state" in wm
        assert "key_facts" in wm
        assert "derived_understanding" in wm

    def test_meta_has_timestamps(self):
        wm = build_world_model(_clean_fcf())
        assert "generated_at" in wm["meta"]
        assert "run_date" in wm["meta"]

    def test_state_has_required_fields(self):
        wm = build_world_model(_clean_fcf())
        state = wm["state"]
        assert state["company"] == "Dominion Energy"
        assert state["ticker"] == "D"
        assert state["filing_type"] == "10-K"
        assert state["reporting_period"] == "2024-12-31"

    def test_key_facts_all_present(self):
        wm = build_world_model(_clean_fcf())
        facts = wm["key_facts"]
        assert facts["revenue"] == 15_200_000_000
        assert facts["net_income"] == 2_100_000_000
        assert facts["operating_cash_flow"] == 4_100_000_000
        assert facts["capex"] == 3_800_000_000
        assert facts["fcf"] == 300_000_000
        assert abs(facts["fcf_margin"] - 0.0197) < 1e-6

    def test_derived_understanding_is_list(self):
        wm = build_world_model(_clean_fcf())
        assert isinstance(wm["derived_understanding"], list)
        assert len(wm["derived_understanding"]) > 0

    def test_status_parsed_when_no_errors(self):
        wm = build_world_model(_clean_fcf(errors=[]))
        assert wm["state"]["status"] == "Parsed"

    def test_status_partial_when_errors(self):
        wm = build_world_model(_clean_fcf(errors=["ocf missing"]))
        assert wm["state"]["status"] == "Partial"


# ---------------------------------------------------------------------------
# Derived understanding rules
# ---------------------------------------------------------------------------

class TestDerivedUnderstanding:
    def test_low_fcf_margin_flagged(self):
        insights = _derive_understanding({
            "revenue": 10_000_000_000,
            "operating_cash_flow": 2_000_000_000,
            "capex": 1_800_000_000,
            "fcf_margin": 0.02,   # 2% < 5% threshold
            "net_income": 500_000_000,
        })
        assert any("low" in i.lower() or "limited" in i.lower() for i in insights)

    def test_healthy_fcf_margin_positive(self):
        insights = _derive_understanding({
            "revenue": 10_000_000_000,
            "operating_cash_flow": 3_000_000_000,
            "capex": 1_000_000_000,
            "fcf_margin": 0.20,   # 20% — healthy
            "net_income": 2_000_000_000,
        })
        assert any("healthy" in i.lower() for i in insights)

    def test_high_capex_vs_ocf_flagged(self):
        insights = _derive_understanding({
            "revenue": 10_000_000_000,
            "operating_cash_flow": 2_000_000_000,
            "capex": 1_900_000_000,   # 95% of OCF → high
            "fcf_margin": 0.005,
            "net_income": 100_000_000,
        })
        assert any("high capex" in i.lower() or "capital-intensive" in i.lower() or "high" in i.lower() for i in insights)

    def test_net_loss_flagged(self):
        insights = _derive_understanding({
            "revenue": 10_000_000_000,
            "operating_cash_flow": 500_000_000,
            "capex": 400_000_000,
            "fcf_margin": 0.01,
            "net_income": -500_000_000,   # net loss
        })
        assert any("loss" in i.lower() or "profitab" in i.lower() for i in insights)

    def test_none_values_do_not_raise(self):
        insights = _derive_understanding({
            "revenue": None,
            "operating_cash_flow": None,
            "capex": None,
            "fcf_margin": None,
            "net_income": None,
        })
        assert isinstance(insights, list)
        assert len(insights) > 0

    def test_insufficient_data_fallback(self):
        insights = _derive_understanding({})
        assert any("insufficient" in i.lower() for i in insights)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestWorldModelPersistence:
    def test_world_model_json_written(self, tmp_path):
        build_world_model(_clean_fcf(), run_dir=str(tmp_path))
        out = tmp_path / "world_model.json"
        assert out.exists()

    def test_world_model_json_valid(self, tmp_path):
        build_world_model(_clean_fcf(), run_dir=str(tmp_path))
        data = json.loads((tmp_path / "world_model.json").read_text())
        assert "key_facts" in data
        assert data["key_facts"]["fcf"] == 300_000_000

    def test_no_persist_when_run_dir_none(self):
        # Should not raise; no file written to CWD
        wm = build_world_model(_clean_fcf(), run_dir=None)
        assert wm is not None
