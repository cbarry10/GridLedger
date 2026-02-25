from gridledger.config.settings import SCENARIOS


def estimate_revenue(metrics, scenario="base"):
    """
    AC3 — Revenue Modeling Logic
    Estimates battery revenue using scenario assumptions.
    """

    if scenario not in SCENARIOS:
        raise ValueError(f"Scenario '{scenario}' not found in settings.")

    assumptions = SCENARIOS[scenario]

    battery_mwh = assumptions["battery_mwh"]
    efficiency = assumptions["efficiency"]
    cycles = assumptions["cycles"]

    avg_price = metrics["average_price"]
    price_range = metrics["price_range"]

    # Simple revenue proxy
    simple_revenue = avg_price * battery_mwh

    # Arbitrage proxy
    arbitrage_revenue = price_range * battery_mwh * efficiency * cycles

    results = {
        "scenario": scenario,
        "battery_size_mwh": battery_mwh,
        "efficiency": efficiency,
        "cycles_per_day": cycles,
        "simple_revenue_estimate": round(simple_revenue, 2),
        "arbitrage_proxy_revenue": round(arbitrage_revenue, 2),
    }

    print("\n[AC3] Revenue estimates computed")
    print(results)

    return results

