import pandas as pd


def compute_price_metrics(df):
    """
    AC2 — Compute summary price metrics from hourly LMP data
    """

    # Drop missing values
    df = df.dropna(subset=["lmp"])

    avg_price = df["lmp"].mean()
    min_price = df["lmp"].min()
    max_price = df["lmp"].max()
    price_range = max_price - min_price
    volatility = df["lmp"].std()

    metrics = {
        "average_price": float(round(avg_price, 2)),
        "min_price": float(round(min_price, 2)),
        "max_price": float(round(max_price, 2)),
        "price_range": float(round(price_range, 2)),
        "volatility": float(round(volatility, 2)),
        "observations": int(len(df)),
    }

    print("\n[AC2] Metrics computed successfully")
    print(metrics)

    return metrics
