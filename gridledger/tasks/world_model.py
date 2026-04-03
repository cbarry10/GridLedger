# gridledger/tasks/world_model.py
#
# Layer 3 — World Model
#
# Builds a persistent JSON "snapshot" of what Cortex currently knows about
# Dominion Energy.  All facts are grounded in computed values — no LLM.
#
# Output schema:
# {
#   "meta":    {"generated_at": ..., "run_date": ...},
#   "state":   {"company", "ticker", "filing_type", "reporting_period", "status"},
#   "key_facts": {revenue, net_income, operating_cash_flow, capex, fcf, fcf_margin},
#   "derived_understanding": [<rule-based classification strings>]
# }

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from gridledger.config.settings import (
    DOMINION_NAME,
    DOMINION_TICKER,
)

logger = logging.getLogger(__name__)

# Rule thresholds
_REGULATED_UTILITY_CAPEX_RATIO = 0.50   # CapEx > 50% of revenue → regulated utility
_HIGH_CAPEX_OCF_RATIO = 0.80            # CapEx > 80% OCF → high CapEx relative to cash
_LOW_FCF_MARGIN = 0.05                   # FCF margin < 5% → capital pressure
_MOD_FCF_MARGIN = 0.10                   # FCF margin < 10% → moderate


def build_world_model(fcf_output: dict, run_dir: str | None = None) -> dict:
    """
    Construct the World Model dict from FCF computation output.

    Args:
        fcf_output:  Output of compute_fcf()
        run_dir:     If provided, write world_model.json to this directory

    Returns:
        World Model dict
    """
    now = datetime.now(timezone.utc).isoformat()
    today = datetime.now(timezone.utc).date().isoformat()

    status = "Parsed" if not fcf_output.get("errors") else "Partial"

    key_facts = {
        "revenue":              fcf_output.get("revenue"),
        "net_income":           fcf_output.get("net_income"),
        "operating_cash_flow":  fcf_output.get("operating_cash_flow"),
        "capex":                fcf_output.get("capex"),
        "fcf":                  fcf_output.get("fcf"),
        "fcf_margin":           fcf_output.get("fcf_margin"),
    }

    derived = _derive_understanding(key_facts)

    world_model = {
        "meta": {
            "generated_at": now,
            "run_date": today,
        },
        "state": {
            "company":          DOMINION_NAME,
            "ticker":           DOMINION_TICKER,
            "filing_type":      "10-K",
            "reporting_period": fcf_output.get("reporting_period"),
            "status":           status,
        },
        "key_facts": key_facts,
        "derived_understanding": derived,
    }

    if run_dir:
        _persist(world_model, Path(run_dir))

    logger.info(
        "World Model built: status=%s, derived_insights=%d",
        status, len(derived),
    )
    return world_model


def _derive_understanding(facts: dict) -> list[str]:
    """
    Apply rule-based classifiers to produce human-readable insight strings.
    All thresholds are deterministic — no LLM.
    """
    insights: list[str] = []

    revenue = facts.get("revenue")
    ocf = facts.get("operating_cash_flow")
    capex = facts.get("capex")
    fcf_margin = facts.get("fcf_margin")
    net_income = facts.get("net_income")

    # Business model classification
    if revenue and capex and (capex / revenue) > _REGULATED_UTILITY_CAPEX_RATIO:
        insights.append("Regulated utility — capital-intensive business model")

    # CapEx intensity vs OCF
    if ocf and capex:
        ratio = capex / ocf
        if ratio > _HIGH_CAPEX_OCF_RATIO:
            insights.append(
                f"High CapEx relative to operating cash flow ({ratio:.0%} of OCF)"
            )

    # FCF margin classification
    if fcf_margin is not None:
        if fcf_margin < _LOW_FCF_MARGIN:
            insights.append(
                f"Low free cash flow margin ({fcf_margin:.2%}) — limited financial flexibility"
            )
        elif fcf_margin < _MOD_FCF_MARGIN:
            insights.append(
                f"Moderate free cash flow margin ({fcf_margin:.2%})"
            )
        else:
            insights.append(
                f"Healthy free cash flow margin ({fcf_margin:.2%})"
            )

    # Net income
    if net_income is not None and net_income < 0:
        insights.append("Net loss reported — profitability concern")

    if not insights:
        insights.append("Insufficient data for classification")

    return insights


def _persist(world_model: dict, run_dir: Path) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    out_path = run_dir / "world_model.json"
    out_path.write_text(json.dumps(world_model, indent=2), encoding="utf-8")
    logger.info("World Model persisted to %s", out_path)
