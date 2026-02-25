import json
from pathlib import Path
from datetime import datetime
import pandas as pd

from gridledger.config.settings import OUTPUT_DIR


def save_structured_outputs(metrics, revenue, memo, df):
    """
    Saves all AC6 outputs:
    - JSON summary
    - CSV metrics
    - Text report
    """

    # Create dated output directory
    run_date = datetime.now().strftime("%Y-%m-%d")
    run_dir = OUTPUT_DIR / run_date
    run_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().isoformat()

    # ------------------------
    # JSON Output
    # ------------------------
    json_output = {
        "timestamp": timestamp,
        "metrics": metrics,
        "revenue": revenue,
        "memo": memo,
    }

    json_path = run_dir / "summary.json"
    with open(json_path, "w") as f:
        json.dump(json_output, f, indent=4)

    # ------------------------
    # CSV Output
    # ------------------------
    metrics_df = pd.DataFrame([metrics])
    csv_path = run_dir / "metrics.csv"
    metrics_df.to_csv(csv_path, index=False)

    # ------------------------
    # Text Report
    # ------------------------
    report_path = run_dir / "report.txt"

    report_text = f"""
GRIDLEDGER REVENUE SNAPSHOT
Timestamp: {timestamp}

Average Price: {metrics['average_price']}
Min Price: {metrics['min_price']}
Max Price: {metrics['max_price']}
Price Range: {metrics['price_range']}
Volatility: {metrics['volatility']}
Risk Level: {metrics.get('risk_level', 'N/A')}

Revenue Estimate:
Simple Revenue: {revenue['simple_revenue_estimate']}
Arbitrage Proxy: {revenue['arbitrage_proxy_revenue']}

AI Memo:
{memo}
"""

    with open(report_path, "w") as f:
        f.write(report_text)

    print(f"\n[AC6] Outputs saved to: {run_dir}")
