import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, render_template, send_file

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "outputs"
DATA_DIR = PROJECT_ROOT / "data"

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Helpers — mirrors format_executive_summary() logic from main.py
# ---------------------------------------------------------------------------

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

    return f"{base} {' '.join(additions)}" if additions else base


def _build_investment_view(volatility, arbitrage_revenue, simple_revenue):
    sentences = []
    if volatility <= 20:
        sentences.append(
            "The market shows enough volatility to support storage-based arbitrage, "
            "but outcomes depend on disciplined operations."
        )
    else:
        sentences.append(
            "The market offers strong spread potential, but revenue variability is elevated "
            "and requires tighter risk controls."
        )

    if simple_revenue > 0 and arbitrage_revenue >= (simple_revenue * 2):
        sentences.append(
            "Revenue performance appears highly dependent on active dispatch rather than "
            "passive exposure to average pricing."
        )
    else:
        sentences.append(
            "Revenue appears less dependent on aggressive dispatch, with a more balanced "
            "contribution from baseline price levels."
        )

    sentences.append(
        "Further diligence should focus on dispatch strategy, degradation economics, "
        "and seasonal stability."
    )
    return " ".join(sentences)


def reconstruct_slack_output(data):
    """Reconstruct the exact text that was sent to Slack from summary.json data."""
    m = data["metrics"]
    r = data["revenue"]

    run_ts = datetime.fromisoformat(data["timestamp"])
    end_date = run_ts.date().isoformat()
    start_date = (run_ts.date() - timedelta(days=7)).isoformat()

    efficiency_pct = int(round(float(r["efficiency"]) * 100))
    interpretation = _build_interpretation(
        volatility=float(m["volatility"]),
        average_price=float(m["average_price"]),
        min_price=float(m["min_price"]),
        arbitrage_revenue=float(r["arbitrage_proxy_revenue"]),
        simple_revenue=float(r["simple_revenue_estimate"]),
    )
    investment_view = _build_investment_view(
        volatility=float(m["volatility"]),
        arbitrage_revenue=float(r["arbitrage_proxy_revenue"]),
        simple_revenue=float(r["simple_revenue_estimate"]),
    )

    return (
        "GridLedger | Revenue Snapshot\n"
        "CAISO Day-Ahead Market\n"
        f"Period: {_format_date(start_date)}-{_format_date(end_date)}\n\n"
        "Market Overview\n"
        f"• Average Price: {_format_money(m['average_price'])}/MWh\n"
        f"• Range: {_format_money(m['min_price'])} -> {_format_money(m['max_price'])} "
        f"({_format_money(m['price_range'])} spread)\n"
        f"• Volatility: {float(m['volatility']):.2f}\n"
        f"• Observations: {int(m['observations']):,}\n\n"
        "Interpretation:\n"
        f"{interpretation}\n\n"
        "Risk Assessment\n"
        f"• Risk Level: {m['risk_level']}\n\n"
        f"Revenue Profile ({r['battery_size_mwh']} MWh Battery)\n"
        f"• Cycle Assumption: {float(r['cycles_per_day']):.1f} cycle/day\n"
        f"• Efficiency: {efficiency_pct}%\n\n"
        f"• Simple Revenue: {_format_money(r['simple_revenue_estimate'])}\n"
        f"• Arbitrage Revenue: {_format_money(r['arbitrage_proxy_revenue'])}\n\n"
        "Investment View\n"
        f"{investment_view}\n\n"
        "System Notes\n"
        "• Source: CAISO DAM\n"
        f"• Dataset: {int(m['observations']):,} hourly observations\n"
        "• Output archived successfully"
    )


def _latest_run_dir():
    """Return the Path of the most recent dated output folder, or None."""
    dated = sorted(OUTPUT_DIR.glob("20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]"))
    return dated[-1] if dated else None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/runs")
def api_runs():
    """List all available dated run folders."""
    dated = sorted(OUTPUT_DIR.glob("20[0-9][0-9]-[0-9][0-9]-[0-9][0-9]"), reverse=True)
    return jsonify([d.name for d in dated])


@app.route("/api/latest")
def api_latest():
    """Return latest run summary + reconstructed Slack output."""
    run_dir = _latest_run_dir()
    if run_dir is None:
        return jsonify({"error": "No run data found. Run the pipeline first."}), 404

    summary_path = run_dir / "summary.json"
    if not summary_path.exists():
        return jsonify({"error": f"summary.json missing in {run_dir.name}"}), 404

    with open(summary_path) as f:
        data = json.load(f)

    data["run_date"] = run_dir.name
    data["slack_output"] = reconstruct_slack_output(data)
    return jsonify(data)


@app.route("/api/prices")
def api_prices():
    """Return hourly LMP data pivoted by node for Chart.js."""
    csv_path = DATA_DIR / "hourly_lmp.csv"
    if not csv_path.exists():
        return jsonify({"error": "No price data found. Run the pipeline first."}), 404

    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["lmp"] = pd.to_numeric(df["lmp"], errors="coerce")
    df = df.dropna(subset=["lmp"])

    # Aggregate duplicate (timestamp, node) entries
    df = df.groupby(["timestamp", "node"])["lmp"].mean().reset_index()
    pivot = df.pivot_table(index="timestamp", columns="node", values="lmp", aggfunc="mean")
    pivot = pivot.sort_index()

    labels = [ts.strftime("%Y-%m-%d %H:%M") for ts in pivot.index]
    datasets = {}
    for node in pivot.columns:
        datasets[node] = [
            round(float(v), 4) if pd.notna(v) else None
            for v in pivot[node]
        ]

    return jsonify({"labels": labels, "datasets": datasets})


@app.route("/download/csv")
def download_csv():
    """Download the latest metrics.csv."""
    run_dir = _latest_run_dir()
    if run_dir is None:
        return "No run data found.", 404

    csv_path = run_dir / "metrics.csv"
    if not csv_path.exists():
        return "metrics.csv not found.", 404

    return send_file(
        csv_path,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"gridledger_metrics_{run_dir.name}.csv",
    )


if __name__ == "__main__":
    print("GridLedger Dashboard → http://localhost:5050")
    app.run(host="0.0.0.0", port=5050, debug=False)
