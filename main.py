from gridledger.tasks.ingestion import (
    fetch_caiso_prices,
    normalize_caiso_lmp
)
from gridledger.tasks.metrics import compute_price_metrics
from gridledger.tasks.revenue import estimate_revenue
from gridledger.tasks.risk import classify_volatility_risk
from gridledger.tasks.memo import generate_underwriting_memo  # AC5
from gridledger.tasks.output import save_structured_outputs

from gridledger.config.settings import (
    DEFAULT_START_DATE,
    DEFAULT_END_DATE,
    OUTPUT_DIR
)


def main():

    print("\n--- GridLedger Revenue Snapshot ---")

    # AC1 — Data ingestion
    raw_df = fetch_caiso_prices()

    # Normalize dataset
    df = normalize_caiso_lmp(raw_df)

    # Save clean dataset
    df.to_csv("data/hourly_lmp.csv", index=False)
    print("[AC1] Clean dataset saved to data/hourly_lmp.csv")

    # AC2 — Metrics
    metrics = compute_price_metrics(df)

    print("\n[AC2] Price Metrics Summary")
    for key, value in metrics.items():
        print(f"{key}: {value}")

    # AC4 — Risk classification
    metrics = classify_volatility_risk(metrics)

    print("\n[AC4] Risk Summary")
    print(f"Risk Level: {metrics['risk_level']}")

    # AC3 — Revenue modeling
    scenario = "base"  # conservative | base | aggressive
    revenue = estimate_revenue(metrics, scenario=scenario)

    print("\n[AC3] Revenue Estimates")
    for key, value in revenue.items():
        print(f"{key}: {value}")

    # AC5 — Memo generation
    memo = generate_underwriting_memo(
        metrics=metrics,
        revenue=revenue,
        risk_level=metrics["risk_level"],
        start_date=DEFAULT_START_DATE,
        end_date=DEFAULT_END_DATE
    )

    print("\n[AC5] Underwriting Memo\n")
    print(memo)

    # Save memo to file
    memo_path = OUTPUT_DIR / "memo.txt"
    with open(memo_path, "w") as f:
        f.write(memo)

    print(f"\n[AC5] Memo saved to {memo_path}")
    # AC6 — Structured Outputs
    save_structured_outputs(metrics, revenue, memo, df)

    print("\n--- GridLedger Run Complete ---\n")


if __name__ == "__main__":
    main()






