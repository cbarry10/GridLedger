from contextlib import redirect_stdout
from io import StringIO
from datetime import datetime

from gridledger.tasks.ingestion import fetch_caiso_prices, normalize_caiso_lmp
from gridledger.tasks.metrics import compute_price_metrics
from gridledger.tasks.revenue import estimate_revenue
from gridledger.tasks.risk import classify_volatility_risk
from gridledger.tasks.memo import generate_underwriting_memo
from gridledger.tasks.output import save_structured_outputs
from gridledger.config.settings import DEFAULT_START_DATE, DEFAULT_END_DATE, OUTPUT_DIR

DEBUG = False


def _run_step(step_fn, *args, **kwargs):
    """Runs a step quietly unless DEBUG is enabled."""
    if DEBUG:
        return step_fn(*args, **kwargs)
    with redirect_stdout(StringIO()):
        return step_fn(*args, **kwargs)


def _format_money(value):
    amount = f"{abs(float(value)):.2f}"
    sign = "-" if float(value) < 0 else ""
    return f"{sign}${amount}"


def _format_date(date_value):
    try:
        return datetime.strptime(str(date_value), "%Y-%m-%d").strftime("%B %-d, %Y")
    except ValueError:
        return str(date_value)


def _build_interpretation(volatility, average_price, min_price, arbitrage_revenue, simple_revenue):
    if volatility < 10:
        base = "Relatively stable pricing with limited spread capture opportunity."
    elif volatility <= 20:
        base = "Moderate volatility with visible intraday spread capture opportunity."
    else:
        base = "High volatility with strong arbitrage potential, but elevated revenue variability."

    additions = []
    if average_price < 10:
        additions.append("Baseline pricing remains low.")
    if min_price < 0:
        additions.append("Negative pricing events support storage arbitrage.")
    if simple_revenue > 0 and arbitrage_revenue >= (simple_revenue * 2):
        additions.append("Active dispatch is required to unlock most value.")

    if additions:
        return f"{base} {' '.join(additions)}"
    return base


def _build_investment_view(volatility, arbitrage_revenue, simple_revenue):
    sentences = []
    if volatility <= 20:
        sentences.append(
            "The market shows enough volatility to support storage-based arbitrage, but outcomes depend on disciplined operations."
        )
    else:
        sentences.append(
            "The market offers strong spread potential, but revenue variability is elevated and requires tighter risk controls."
        )

    if simple_revenue > 0 and arbitrage_revenue >= (simple_revenue * 2):
        sentences.append(
            "Revenue performance appears highly dependent on active dispatch rather than passive exposure to average pricing."
        )
    else:
        sentences.append(
            "Revenue appears less dependent on aggressive dispatch, with a more balanced contribution from baseline price levels."
        )

    sentences.append("Further diligence should focus on dispatch strategy, degradation economics, and seasonal stability.")
    return " ".join(sentences)


def format_executive_summary(
    start_date,
    end_date,
    average_price,
    min_price,
    max_price,
    price_range,
    volatility,
    observations,
    risk_level,
    battery_size_mwh,
    efficiency,
    cycles_per_day,
    simple_revenue_estimate,
    arbitrage_proxy_revenue,
):
    efficiency_pct = int(round(float(efficiency) * 100))
    interpretation = _build_interpretation(
        volatility=float(volatility),
        average_price=float(average_price),
        min_price=float(min_price),
        arbitrage_revenue=float(arbitrage_proxy_revenue),
        simple_revenue=float(simple_revenue_estimate),
    )
    investment_view = _build_investment_view(
        volatility=float(volatility),
        arbitrage_revenue=float(arbitrage_proxy_revenue),
        simple_revenue=float(simple_revenue_estimate),
    )

    return (
        "GridLedger | Revenue Snapshot\n"
        "CAISO Day-Ahead Market\n"
        f"Period: {_format_date(start_date)}-{_format_date(end_date)}\n\n"
        "Market Overview\n"
        f"• Average Price: {_format_money(average_price)}/MWh\n"
        f"• Range: {_format_money(min_price)} -> {_format_money(max_price)} ({_format_money(price_range)} spread)\n"
        f"• Volatility: {float(volatility):.2f}\n"
        f"• Observations: {int(observations):,}\n\n"
        "Interpretation:\n"
        f"{interpretation}\n\n"
        "Risk Assessment\n"
        f"• Risk Level: {risk_level}\n\n"
        f"Revenue Profile ({battery_size_mwh} MWh Battery)\n"
        f"• Cycle Assumption: {float(cycles_per_day):.1f} cycle/day\n"
        f"• Efficiency: {efficiency_pct}%\n\n"
        f"• Simple Revenue: {_format_money(simple_revenue_estimate)}\n"
        f"• Arbitrage Revenue: {_format_money(arbitrage_proxy_revenue)}\n\n"
        "Investment View\n"
        f"{investment_view}\n\n"
        "System Notes\n"
        "• Source: CAISO DAM\n"
        f"• Dataset: {int(observations):,} hourly observations\n"
        "• Output archived successfully"
    )


def main():
    raw_df = _run_step(fetch_caiso_prices)
    df = _run_step(normalize_caiso_lmp, raw_df)
    df.to_csv("data/hourly_lmp.csv", index=False)

    metrics = _run_step(compute_price_metrics, df)
    metrics = _run_step(classify_volatility_risk, metrics)

    scenario = "base"
    revenue = _run_step(estimate_revenue, metrics, scenario=scenario)

    # Keep memo generation in place for archival/debug workflows, but do not print to Slack output.
    memo = _run_step(
        generate_underwriting_memo,
        metrics=metrics,
        revenue=revenue,
        risk_level=metrics["risk_level"],
        start_date=DEFAULT_START_DATE,
        end_date=DEFAULT_END_DATE,
    )

    memo_path = OUTPUT_DIR / "memo.txt"
    with open(memo_path, "w") as f:
        f.write(memo)

    _run_step(save_structured_outputs, metrics, revenue, memo, df)

    summary = format_executive_summary(
        start_date=DEFAULT_START_DATE,
        end_date=DEFAULT_END_DATE,
        average_price=metrics["average_price"],
        min_price=metrics["min_price"],
        max_price=metrics["max_price"],
        price_range=metrics["price_range"],
        volatility=metrics["volatility"],
        observations=metrics["observations"],
        risk_level=metrics["risk_level"],
        battery_size_mwh=revenue["battery_size_mwh"],
        efficiency=revenue["efficiency"],
        cycles_per_day=revenue["cycles_per_day"],
        simple_revenue_estimate=revenue["simple_revenue_estimate"],
        arbitrage_proxy_revenue=revenue["arbitrage_proxy_revenue"],
    )
    print(summary)


if __name__ == "__main__":
    main()






