# gridledger/tasks/risk.py

from gridledger.config.settings import (
    LOW_VOL_THRESHOLD,
    HIGH_VOL_THRESHOLD,
)


def classify_volatility_risk(metrics):
    """
    AC4 — Risk & Volatility Classification

    Converts volatility into a risk category:
        Low, Medium, High

    Uses deterministic thresholds from settings.py
    """

    volatility = metrics.get("volatility")

    if volatility is None:
        raise ValueError("Volatility metric missing from metrics dictionary")

    # Risk classification logic
    if volatility < LOW_VOL_THRESHOLD:
        risk = "Low"
    elif volatility < HIGH_VOL_THRESHOLD:
        risk = "Medium"
    else:
        risk = "High"

    # Add to structured output
    metrics["risk_level"] = risk

    print("\n[AC4] Risk classification complete")
    print(f"Volatility: {volatility} → Risk Level: {risk}")

    return metrics
