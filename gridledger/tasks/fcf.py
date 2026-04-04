# gridledger/tasks/fcf.py
#
# Layer 2 — Junior Banker (Deterministic FCF Computation)
#
# Computes Free Cash Flow from XBRL-sourced financials.
# NO LLM involvement. All math is deterministic and None-safe.
#
# FCF  = Operating Cash Flow – CapEx
# FCF Margin = FCF / Revenue  (None if revenue is None or zero)

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def compute_fcf(xbrl_facts: dict) -> dict:
    """
    Compute FCF metrics from the output of fetch_xbrl_facts().

    Input format (per key):
        {"value": <int | None>, "tag": <str>, "period": <str>}
        OR {"value": None, "error": <str>}

    Output:
        {
            "revenue":              <int | None>,
            "net_income":           <int | None>,
            "operating_cash_flow":  <int | None>,
            "capex":                <int | None>,
            "fcf":                  <int | None>,
            "fcf_margin":           <float | None>,
            "reporting_period":     <str | None>,
            "errors":               [<str>, ...]   # empty list = clean run
        }
    """
    errors: list[str] = []

    revenue = _val(xbrl_facts, "revenue", errors)
    net_income = _val(xbrl_facts, "net_income", errors)
    ocf = _val(xbrl_facts, "operating_cash_flow", errors)
    capex = _val(xbrl_facts, "capex", errors)

    # FCF
    if ocf is not None and capex is not None:
        fcf = ocf - capex
    else:
        fcf = None
        if ocf is None and capex is None:
            errors.append("FCF not computed: both operating_cash_flow and capex missing")
        elif ocf is None:
            errors.append("FCF not computed: operating_cash_flow missing")
        else:
            errors.append("FCF not computed: capex missing")

    # FCF Margin
    if fcf is not None and revenue is not None and revenue != 0:
        fcf_margin = fcf / revenue
    else:
        fcf_margin = None
        if fcf is not None and revenue is None:
            errors.append("FCF margin not computed: revenue missing")
        elif fcf is not None and revenue == 0:
            errors.append("FCF margin not computed: revenue is zero")

    # Best-effort reporting period from OCF tag (most likely to be populated)
    reporting_period = (
        xbrl_facts.get("operating_cash_flow", {}).get("period")
        or xbrl_facts.get("revenue", {}).get("period")
    )

    result = {
        "revenue": revenue,
        "net_income": net_income,
        "operating_cash_flow": ocf,
        "capex": capex,
        "fcf": fcf,
        "fcf_margin": fcf_margin,
        "reporting_period": reporting_period,
        "errors": errors,
    }

    if errors:
        logger.warning("FCF computation completed with %d error(s): %s", len(errors), errors)
    else:
        logger.info(
            "FCF computed: OCF=%s, CapEx=%s, FCF=%s, Margin=%.2f%%",
            _fmt(ocf), _fmt(capex), _fmt(fcf),
            (fcf_margin * 100) if fcf_margin is not None else 0,
        )

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _val(facts: dict, key: str, errors: list[str]) -> int | None:
    """Extract a numeric value from an xbrl_facts entry; record errors."""
    entry = facts.get(key, {})
    v = entry.get("value")
    if v is None:
        err = entry.get("error", f"{key} not available")
        errors.append(err)
    return v


def _fmt(v: int | None) -> str:
    if v is None:
        return "N/A"
    billions = v / 1_000_000_000
    return f"${billions:.1f}B"
