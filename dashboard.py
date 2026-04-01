# dashboard.py — GridLedger Streamlit Dashboard
# Run: streamlit run dashboard.py --server.port 5050

import json
import io
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DATA_DIR = PROJECT_ROOT / "data"

# ---------------------------------------------------------------------------
# Data loaders (all cached for 5 minutes)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def find_latest_summary() -> dict | None:
    candidates = sorted(OUTPUTS_DIR.glob("*/summary.json"))
    if not candidates:
        return None
    with open(candidates[-1]) as f:
        return json.load(f)


@st.cache_data(ttl=300)
def find_latest_metrics_csv() -> Path | None:
    candidates = sorted(OUTPUTS_DIR.glob("*/metrics.csv"))
    return candidates[-1] if candidates else None


@st.cache_data(ttl=300)
def load_lmp_data() -> pd.DataFrame | None:
    path = DATA_DIR / "hourly_lmp.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df["lmp"] = pd.to_numeric(df["lmp"], errors="coerce")
    return df.dropna(subset=["lmp"])


@st.cache_data(ttl=300)
def _load_run_history():
    try:
        from gridledger.analytics.run_logger import load_run_history
        return load_run_history()
    except Exception:
        return []


@st.cache_data(ttl=300)
def _load_eval_history():
    try:
        from gridledger.analytics.eval_logger import load_eval_history
        return load_eval_history()
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="GridLedger Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("⚡ GridLedger — CAISO Battery Storage Analytics")
st.caption(f"Dashboard refreshed at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Executive Summary",
    "📈 LMP Price Chart",
    "📥 Metrics Export",
    "👥 Usage Analytics",
    "🧪 LLM Eval Scorecard",
])

# ---------------------------------------------------------------------------
# Tab 1 — Executive Summary
# ---------------------------------------------------------------------------

with tab1:
    summary = find_latest_summary()
    if summary is None:
        st.info("No data yet — run `python main.py` first")
    else:
        ts = summary.get("timestamp", "unknown")
        try:
            ts_fmt = datetime.fromisoformat(ts).strftime("%B %-d, %Y at %H:%M UTC")
        except Exception:
            ts_fmt = ts
        st.caption(f"Generated: {ts_fmt}")

        metrics = summary["metrics"]
        revenue = summary["revenue"]

        # Row 1: price metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Avg Price", f"${metrics['average_price']:.2f}/MWh")
        col2.metric("Min Price", f"${metrics['min_price']:.2f}/MWh")
        col3.metric("Max Price", f"${metrics['max_price']:.2f}/MWh")
        col4.metric("Volatility", f"{metrics['volatility']:.2f}")

        # Row 2: revenue + risk
        col5, col6, col7, col8 = st.columns(4)
        col5.metric("Risk Level", metrics["risk_level"])
        col6.metric("Observations", f"{metrics['observations']:,}")
        col7.metric("Simple Revenue", f"${revenue['simple_revenue_estimate']:.2f}")
        col8.metric("Arbitrage Revenue", f"${revenue['arbitrage_proxy_revenue']:.2f}")

        st.divider()
        st.subheader("Investment Memo")
        st.caption(f"Scenario: {revenue['scenario']} · {revenue['battery_size_mwh']} MWh · "
                   f"{int(revenue['efficiency']*100)}% efficiency · "
                   f"{revenue['cycles_per_day']} cycle/day")
        st.markdown(summary["memo"])

# ---------------------------------------------------------------------------
# Tab 2 — 7-Day LMP Price Chart
# ---------------------------------------------------------------------------

with tab2:
    lmp_df = load_lmp_data()
    if lmp_df is None or lmp_df.empty:
        st.info("No LMP data yet — run `python main.py` first")
    else:
        NODE_COLORS = {
            "TH_NP15_GEN-APND": "#1f77b4",
            "TH_SP15_GEN-APND": "#ff7f0e",
            "TH_ZP26_GEN-APND": "#2ca02c",
        }

        fig = px.line(
            lmp_df,
            x="timestamp",
            y="lmp",
            color="node",
            color_discrete_map=NODE_COLORS,
            title="7-Day Hourly LMP by Node ($/MWh)",
            labels={"timestamp": "Hour", "lmp": "LMP ($/MWh)", "node": "Node"},
        )
        fig.add_hline(
            y=0,
            line_dash="dash",
            line_color="red",
            annotation_text="$0 threshold",
            annotation_position="top left",
        )
        fig.update_layout(
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=40, r=20, t=60, b=40),
            height=450,
        )
        st.plotly_chart(fig, width="stretch")

        st.subheader("Node Summary Statistics")
        node_stats = (
            lmp_df.groupby("node")["lmp"]
            .agg(["mean", "min", "max", "std"])
            .rename(columns={"mean": "Avg ($/MWh)", "min": "Min", "max": "Max", "std": "Std Dev"})
            .round(2)
        )
        st.dataframe(node_stats, width="stretch")

# ---------------------------------------------------------------------------
# Tab 3 — Metrics CSV Export
# ---------------------------------------------------------------------------

with tab3:
    csv_path = find_latest_metrics_csv()
    if csv_path is None:
        st.info("No metrics file found — run `python main.py` first")
    else:
        run_date = csv_path.parent.name
        st.subheader("Latest Metrics Export")
        st.caption(f"From run: {run_date}")

        csv_bytes = csv_path.read_bytes()

        st.download_button(
            label="⬇️ Download metrics.csv",
            data=csv_bytes,
            file_name=f"gridledger_metrics_{run_date}.csv",
            mime="text/csv",
        )

        st.divider()
        st.subheader("Preview")
        preview_df = pd.read_csv(io.BytesIO(csv_bytes))
        st.dataframe(preview_df, width="stretch")

# ---------------------------------------------------------------------------
# Tab 4 — Usage Analytics
# ---------------------------------------------------------------------------

with tab4:
    runs = _load_run_history()
    if not runs:
        st.info("No run history yet — run `python main.py` first")
    else:
        run_df = pd.DataFrame(runs)
        run_df["timestamp"] = pd.to_datetime(run_df["timestamp"], utc=True)

        # KPI row
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Runs", len(run_df))
        col2.metric("Unique Users", run_df["user"].nunique())
        col3.metric("Prompt Versions", run_df["prompt_version"].nunique())

        st.divider()

        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("Runs by User")
            user_counts = run_df["user"].value_counts().reset_index()
            user_counts.columns = ["user", "count"]
            fig_user = px.bar(
                user_counts, x="user", y="count",
                labels={"user": "User", "count": "Run Count"},
                color="user",
            )
            fig_user.update_layout(showlegend=False, height=300, margin=dict(t=20, b=40))
            st.plotly_chart(fig_user, width="stretch")

        with col_right:
            st.subheader("Risk Distribution")
            risk_counts = run_df["risk_level"].value_counts().reset_index()
            risk_counts.columns = ["risk_level", "count"]
            RISK_COLORS = {"Low": "#2ca02c", "Medium": "#ff7f0e", "High": "#d62728"}
            fig_risk = px.pie(
                risk_counts, names="risk_level", values="count",
                color="risk_level",
                color_discrete_map=RISK_COLORS,
            )
            fig_risk.update_layout(height=300, margin=dict(t=20, b=20))
            st.plotly_chart(fig_risk, width="stretch")

        st.subheader("Runs by Scenario")
        scenario_counts = run_df["scenario"].value_counts().reset_index()
        scenario_counts.columns = ["scenario", "count"]
        fig_scenario = px.bar(
            scenario_counts, x="scenario", y="count",
            labels={"scenario": "Scenario", "count": "Run Count"},
            color="scenario",
        )
        fig_scenario.update_layout(showlegend=False, height=250, margin=dict(t=10, b=40))
        st.plotly_chart(fig_scenario, width="stretch")

        st.subheader("Recent Runs")
        display_cols = ["timestamp", "user", "scenario", "risk_level",
                        "avg_price", "volatility", "simple_revenue",
                        "arbitrage_revenue", "prompt_version"]
        available_cols = [c for c in display_cols if c in run_df.columns]
        recent = run_df.sort_values("timestamp", ascending=False).head(20)[available_cols]
        st.dataframe(recent, width="stretch")

# ---------------------------------------------------------------------------
# Tab 5 — LLM Eval Scorecard
# ---------------------------------------------------------------------------

with tab5:
    evals = _load_eval_history()
    if not evals:
        st.info("No eval data yet — run `python main.py` first")
    else:
        eval_df = pd.json_normalize(evals)

        score_col_map = {
            "scores.composite_score":     "composite_score",
            "scores.numeric_fidelity":    "numeric_fidelity",
            "scores.risk_tone_alignment": "risk_tone_alignment",
            "scores.length_compliance":   "length_compliance",
            "scores.has_recommendation":  "has_recommendation",
            "scores.hedge_present":       "hedge_present",
            "scores.no_bullets":          "no_bullets",
            "scores.word_count":          "word_count",
        }
        eval_df = eval_df.rename(columns=score_col_map)
        eval_df["timestamp"] = pd.to_datetime(eval_df["timestamp"], utc=True)

        # KPI row
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Composite Score (avg)",
                    f"{eval_df['composite_score'].mean():.3f}" if "composite_score" in eval_df else "N/A")
        col2.metric("Numeric Fidelity (avg)",
                    f"{eval_df['numeric_fidelity'].mean():.3f}" if "numeric_fidelity" in eval_df else "N/A")
        col3.metric("Risk Tone Alignment (avg)",
                    f"{eval_df['risk_tone_alignment'].mean():.3f}" if "risk_tone_alignment" in eval_df else "N/A")
        col4.metric("Total Evaluations", len(eval_df))

        st.divider()

        # Hallucination alerts
        if "numeric_fidelity" in eval_df.columns:
            flagged = eval_df[eval_df["numeric_fidelity"] < 0.6]
            if not flagged.empty:
                st.warning(f"⚠️ Hallucination alert: {len(flagged)} eval(s) with numeric_fidelity < 0.6")
                with st.expander("Show flagged evaluations"):
                    flag_cols = ["timestamp", "run_id", "prompt_version",
                                 "numeric_fidelity", "composite_score"]
                    available = [c for c in flag_cols if c in flagged.columns]
                    st.dataframe(flagged[available], width="stretch")

        # Composite score over time
        st.subheader("Composite Score Over Time")
        if "composite_score" in eval_df.columns:
            fig_score = px.line(
                eval_df.sort_values("timestamp"),
                x="timestamp",
                y="composite_score",
                color="prompt_version",
                markers=True,
                labels={
                    "timestamp": "Evaluation Time",
                    "composite_score": "Composite Score",
                    "prompt_version": "Prompt Version",
                },
            )
            fig_score.add_hline(
                y=0.7,
                line_dash="dash",
                line_color="orange",
                annotation_text="Target (0.70)",
                annotation_position="top left",
            )
            fig_score.update_layout(height=350, margin=dict(t=20, b=40))
            st.plotly_chart(fig_score, width="stretch")

        # Per-prompt-version aggregate table
        st.subheader("Scores by Prompt Version")
        score_cols = ["composite_score", "numeric_fidelity", "risk_tone_alignment",
                      "length_compliance", "has_recommendation", "hedge_present", "no_bullets"]
        available_score_cols = [c for c in score_cols if c in eval_df.columns]
        if available_score_cols and "prompt_version" in eval_df.columns:
            version_table = (
                eval_df.groupby("prompt_version")[available_score_cols]
                .mean()
                .round(3)
            )
            st.dataframe(version_table, width="stretch")

        # Metric guide
        with st.expander("Metric definitions"):
            st.markdown("""
| Metric | Weight | Description |
|---|---|---|
| `numeric_fidelity` | 35% | Fraction of key input numbers appearing in memo — primary hallucination detector |
| `risk_tone_alignment` | 25% | Memo tone keywords match computed risk level |
| `length_compliance` | 15% | Output ≤ 200 words per prompt spec |
| `has_recommendation` | 10% | Directional investment language present |
| `hedge_present` | 10% | Uncertainty qualifiers present (calibration) |
| `no_bullets` | 5% | Prose-only format respected |
| `composite_score` | — | Weighted aggregate of above (0.0–1.0) |

*Enable LLM-as-judge scoring: `GRIDLEDGER_LLM_EVAL=1 python main.py`*
            """)
