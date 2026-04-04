# dashboard.py — Cortex AI Financial Intelligence System
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
    # Walk newest-first; skip old CAISO-format summaries (they have 'metrics' key, not 'fcf')
    candidates = sorted(OUTPUTS_DIR.glob("*/summary.json"), reverse=True)
    for path in candidates:
        try:
            with open(path) as f:
                data = json.load(f)
            if "fcf" in data:   # Cortex v3 format
                return data
        except Exception:
            continue
    return None


@st.cache_data(ttl=300)
def find_latest_world_model() -> dict | None:
    candidates = sorted(OUTPUTS_DIR.glob("*/world_model.json"))
    if not candidates:
        return None
    with open(candidates[-1]) as f:
        return json.load(f)


@st.cache_data(ttl=300)
def find_latest_signals() -> dict | None:
    candidates = sorted(OUTPUTS_DIR.glob("*/signals.json"))
    if not candidates:
        return None
    with open(candidates[-1]) as f:
        return json.load(f)


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
    page_title="Cortex — AI Financial Intelligence",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.title("🧠 Cortex — AI Financial Intelligence System")
st.caption(
    f"Dominion Energy (D) · SEC 10-K · "
    f"Dashboard refreshed at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
)

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📋 Executive Summary",
    "📈 FCF History",
    "📥 Data Export",
    "👥 Usage Analytics",
    "🧪 Eval Scorecard",
    "🌐 World Model",
    "⚡ Signals",
])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(v: int | None) -> str:
    if v is None:
        return "N/A"
    if abs(v) >= 1_000_000_000:
        return f"${v / 1_000_000_000:.1f}B"
    return f"${v / 1_000_000:.1f}M"


def _fmt_pct(v: float | None) -> str:
    return f"{v:.2%}" if v is not None else "N/A"


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
        st.caption(f"Generated: {ts_fmt} · Period: {summary.get('reporting_period', 'N/A')}")

        fcf = summary.get("fcf", {})
        signals = summary.get("signals", {})

        # Row 1: computed financials
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Revenue", _fmt(fcf.get("revenue")))
        col2.metric("Operating Cash Flow", _fmt(fcf.get("operating_cash_flow")))
        col3.metric("CapEx", _fmt(fcf.get("capex")))
        col4.metric("Free Cash Flow", _fmt(fcf.get("fcf")))

        # Row 2: margins + signals
        col5, col6, col7, col8 = st.columns(4)
        col5.metric("FCF Margin", _fmt_pct(fcf.get("fcf_margin")))
        col6.metric("Net Income", _fmt(fcf.get("net_income")))
        col7.metric("Signal Count", signals.get("signal_count", 0))
        col8.metric("Reporting Period", summary.get("reporting_period", "N/A"))

        st.divider()

        if signals.get("next_best_action"):
            st.info(f"⚡ **Next Best Action:** {signals['next_best_action']}")

        st.subheader("Investment Memo")
        memo_text = summary.get("memo", "_No memo generated_")
        # Escape bare $ so Streamlit doesn't render them as LaTeX math
        st.markdown(memo_text.replace("$", r"\$"))

        if fcf.get("errors"):
            with st.expander("⚠️ Computation warnings"):
                for err in fcf["errors"]:
                    st.warning(err)

# ---------------------------------------------------------------------------
# Tab 2 — FCF History (run log)
# ---------------------------------------------------------------------------

with tab2:
    runs = _load_run_history()
    if not runs:
        st.info("No run history yet — run `python main.py` first")
    else:
        run_df = pd.DataFrame(runs)
        run_df["timestamp"] = pd.to_datetime(run_df.get("timestamp", []), utc=True, errors="coerce")

        numeric_cols = ["revenue", "net_income", "operating_cash_flow", "capex", "fcf", "fcf_margin"]
        for col in numeric_cols:
            if col in run_df.columns:
                run_df[col] = pd.to_numeric(run_df[col], errors="coerce")

        if "fcf" in run_df.columns and not run_df["fcf"].dropna().empty:
            st.subheader("Free Cash Flow Over Time")
            fig_fcf = px.bar(
                run_df.dropna(subset=["fcf"]).sort_values("timestamp"),
                x="timestamp",
                y="fcf",
                labels={"timestamp": "Run Date", "fcf": "FCF ($)"},
                color_discrete_sequence=["#1f77b4"],
            )
            fig_fcf.add_hline(y=0, line_dash="dash", line_color="red")
            fig_fcf.update_layout(height=350, margin=dict(t=20, b=40))
            st.plotly_chart(fig_fcf, use_container_width=True)

        if "fcf_margin" in run_df.columns and not run_df["fcf_margin"].dropna().empty:
            st.subheader("FCF Margin Over Time")
            fig_margin = px.line(
                run_df.dropna(subset=["fcf_margin"]).sort_values("timestamp"),
                x="timestamp",
                y="fcf_margin",
                markers=True,
                labels={"timestamp": "Run Date", "fcf_margin": "FCF Margin"},
            )
            fig_margin.add_hline(
                y=0.05,
                line_dash="dash",
                line_color="orange",
                annotation_text="5% threshold",
                annotation_position="top left",
            )
            fig_margin.update_layout(height=300, margin=dict(t=20, b=40))
            st.plotly_chart(fig_margin, use_container_width=True)

        st.subheader("All Runs")
        display_cols = ["timestamp", "ticker", "reporting_period", "revenue", "fcf",
                        "fcf_margin", "signal_count", "prompt_version"]
        available = [c for c in display_cols if c in run_df.columns]
        st.dataframe(run_df.sort_values("timestamp", ascending=False)[available].head(20),
                     use_container_width=True)

# ---------------------------------------------------------------------------
# Tab 3 — Data Export
# ---------------------------------------------------------------------------

with tab3:
    summary = find_latest_summary()
    if summary is None:
        st.info("No data yet — run `python main.py` first")
    else:
        st.subheader("Export Latest Run Data")
        run_date = datetime.utcnow().strftime("%Y-%m-%d")

        # Full summary JSON
        summary_bytes = json.dumps(summary, indent=2).encode()
        st.download_button(
            label="⬇️ Download summary.json",
            data=summary_bytes,
            file_name=f"cortex_summary_{run_date}.json",
            mime="application/json",
        )

        wm = summary.get("world_model", {})
        if wm:
            wm_bytes = json.dumps(wm, indent=2).encode()
            st.download_button(
                label="⬇️ Download world_model.json",
                data=wm_bytes,
                file_name=f"cortex_world_model_{run_date}.json",
                mime="application/json",
            )

        # FCF as CSV
        fcf = summary.get("fcf", {})
        if fcf:
            fcf_row = {k: v for k, v in fcf.items() if k != "errors"}
            fcf_df = pd.DataFrame([fcf_row])
            st.download_button(
                label="⬇️ Download fcf_metrics.csv",
                data=fcf_df.to_csv(index=False).encode(),
                file_name=f"cortex_fcf_{run_date}.csv",
                mime="text/csv",
            )

            st.divider()
            st.subheader("FCF Metrics Preview")
            st.dataframe(fcf_df, use_container_width=True)

# ---------------------------------------------------------------------------
# Tab 4 — Usage Analytics
# ---------------------------------------------------------------------------

with tab4:
    runs = _load_run_history()
    if not runs:
        st.info("No run history yet — run `python main.py` first")
    else:
        run_df = pd.DataFrame(runs)
        run_df["timestamp"] = pd.to_datetime(run_df.get("timestamp", []), utc=True, errors="coerce")

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Runs", len(run_df))
        col2.metric("Unique Users", run_df["user"].nunique() if "user" in run_df else "N/A")
        col3.metric("Prompt Versions", run_df["prompt_version"].nunique() if "prompt_version" in run_df else "N/A")

        st.divider()

        col_left, col_right = st.columns(2)
        with col_left:
            if "signal_count" in run_df.columns:
                st.subheader("Signal Count Over Time")
                fig_sig = px.bar(
                    run_df.sort_values("timestamp"),
                    x="timestamp",
                    y="signal_count",
                    labels={"timestamp": "Run Date", "signal_count": "Signals"},
                    color_discrete_sequence=["#ff7f0e"],
                )
                fig_sig.update_layout(height=280, margin=dict(t=20, b=40))
                st.plotly_chart(fig_sig, use_container_width=True)

        with col_right:
            if "memo_word_count" in run_df.columns:
                st.subheader("Memo Length Over Time")
                fig_words = px.line(
                    run_df.sort_values("timestamp"),
                    x="timestamp",
                    y="memo_word_count",
                    markers=True,
                    labels={"timestamp": "Run Date", "memo_word_count": "Words"},
                )
                fig_words.add_hline(y=400, line_dash="dash", line_color="orange",
                                    annotation_text="400w target")
                fig_words.update_layout(height=280, margin=dict(t=20, b=40))
                st.plotly_chart(fig_words, use_container_width=True)

        st.subheader("Recent Runs")
        display_cols = ["timestamp", "user", "ticker", "reporting_period",
                        "fcf", "fcf_margin", "signal_count", "prompt_version"]
        available = [c for c in display_cols if c in run_df.columns]
        st.dataframe(run_df.sort_values("timestamp", ascending=False).head(20)[available],
                     use_container_width=True)

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
            "scores.composite_score":  "composite_score",
            "scores.numeric_fidelity": "numeric_fidelity",
            "scores.section_coverage": "section_coverage",
            "scores.length_compliance": "length_compliance",
            "scores.has_recommendation": "has_recommendation",
            "scores.hedge_present":     "hedge_present",
            "scores.word_count":        "word_count",
        }
        eval_df = eval_df.rename(columns=score_col_map)
        eval_df["timestamp"] = pd.to_datetime(eval_df["timestamp"], utc=True, errors="coerce")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Composite Score (avg)",
                    f"{eval_df['composite_score'].mean():.3f}" if "composite_score" in eval_df else "N/A")
        col2.metric("Numeric Fidelity (avg)",
                    f"{eval_df['numeric_fidelity'].mean():.3f}" if "numeric_fidelity" in eval_df else "N/A")
        col3.metric("Section Coverage (avg)",
                    f"{eval_df['section_coverage'].mean():.3f}" if "section_coverage" in eval_df else "N/A")
        col4.metric("Total Evaluations", len(eval_df))

        st.divider()

        if "numeric_fidelity" in eval_df.columns:
            flagged = eval_df[eval_df["numeric_fidelity"] < 0.6]
            if not flagged.empty:
                st.warning(f"⚠️ Numeric fidelity alert: {len(flagged)} eval(s) below 0.6")
                with st.expander("Show flagged evaluations"):
                    flag_cols = ["timestamp", "run_id", "prompt_version",
                                 "numeric_fidelity", "composite_score"]
                    available = [c for c in flag_cols if c in flagged.columns]
                    st.dataframe(flagged[available], use_container_width=True)

        if "composite_score" in eval_df.columns:
            st.subheader("Composite Score Over Time")
            fig_score = px.line(
                eval_df.sort_values("timestamp"),
                x="timestamp",
                y="composite_score",
                color="prompt_version" if "prompt_version" in eval_df else None,
                markers=True,
                labels={"timestamp": "Evaluation Time", "composite_score": "Composite Score"},
            )
            fig_score.add_hline(y=0.7, line_dash="dash", line_color="orange",
                                annotation_text="Target (0.70)")
            fig_score.update_layout(height=350, margin=dict(t=20, b=40))
            st.plotly_chart(fig_score, use_container_width=True)

        with st.expander("Metric definitions"):
            st.markdown("""
| Metric | Weight | Description |
|---|---|---|
| `numeric_fidelity` | 30% | Source financial values appear in memo within 1% tolerance |
| `section_coverage` | 30% | All 5 required sections present (Business Overview, Financial Performance, Capital Allocation, Key Risks, Investment Signal) |
| `has_recommendation` | 15% | Directional investment language present |
| `length_compliance` | 15% | Output ≤ 400 words per prompt spec |
| `hedge_present` | 10% | Uncertainty qualifiers present |
| `composite_score` | — | Weighted aggregate (0.0–1.0) |

*Enable LLM-as-judge: `GRIDLEDGER_LLM_EVAL=1 python main.py`*
            """)

# ---------------------------------------------------------------------------
# Tab 6 — World Model
# ---------------------------------------------------------------------------

with tab6:
    wm = find_latest_world_model()
    if wm is None:
        # Fall back to summary.world_model
        summary = find_latest_summary()
        wm = summary.get("world_model") if summary else None

    if wm is None:
        st.info("No World Model yet — run `python main.py` first")
    else:
        meta = wm.get("meta", {})
        state = wm.get("state", {})
        facts = wm.get("key_facts", {})
        derived = wm.get("derived_understanding", [])

        st.caption(
            f"Generated: {meta.get('generated_at', 'N/A')} · "
            f"Status: **{state.get('status', 'N/A')}** · "
            f"Period: {state.get('reporting_period', 'N/A')}"
        )

        # Identity row
        col1, col2, col3 = st.columns(3)
        col1.metric("Company", state.get("company", "N/A"))
        col2.metric("Ticker", state.get("ticker", "N/A"))
        col3.metric("Filing Type", state.get("filing_type", "N/A"))

        st.divider()
        st.subheader("📊 Key Facts")

        col1, col2, col3 = st.columns(3)
        col1.metric("Revenue", _fmt(facts.get("revenue")))
        col1.metric("Net Income", _fmt(facts.get("net_income")))
        col2.metric("Operating Cash Flow", _fmt(facts.get("operating_cash_flow")))
        col2.metric("CapEx", _fmt(facts.get("capex")))
        col3.metric("Free Cash Flow", _fmt(facts.get("fcf")))
        col3.metric("FCF Margin", _fmt_pct(facts.get("fcf_margin")))

        st.divider()
        st.subheader("🔍 Derived Understanding")
        st.caption("Rule-based classifications from computed facts — no LLM involvement")

        for insight in derived:
            if "low" in insight.lower() or "loss" in insight.lower() or "negative" in insight.lower():
                st.warning(f"⚠️ {insight}")
            elif "high" in insight.lower() or "capital-intensive" in insight.lower():
                st.info(f"ℹ️ {insight}")
            else:
                st.success(f"✓ {insight}")

        with st.expander("View raw world_model.json"):
            st.json(wm)

# ---------------------------------------------------------------------------
# Tab 7 — Signals
# ---------------------------------------------------------------------------

with tab7:
    sig = find_latest_signals()
    if sig is None:
        summary = find_latest_summary()
        sig = summary.get("signals") if summary else None

    if sig is None:
        st.info("No signals yet — run `python main.py` first")
    else:
        signal_list = sig.get("signals", [])
        nba = sig.get("next_best_action", "N/A")
        signal_count = sig.get("signal_count", len(signal_list))

        # KPI
        col1, col2 = st.columns(2)
        col1.metric("Active Signals", signal_count)
        col2.metric("Prior Period Available", "Yes" if sig.get("prior_period_available") else "No")

        st.divider()

        if signal_list:
            st.subheader(f"⚡ Active Signals ({signal_count})")
            for signal in signal_list:
                st.error(f"🔴 {signal}")
        else:
            st.success("✅ No signals detected — metrics within normal thresholds")

        st.divider()

        st.subheader("🎯 Next Best Action")
        st.info(f"**{nba}**")

        st.divider()
        st.subheader("Signal Definitions")
        with st.expander("Show thresholds"):
            st.markdown("""
| Signal | Threshold | Source |
|---|---|---|
| Low FCF Margin | FCF Margin < 5.0% | Computed FCF / Revenue |
| High CapEx / OCF | CapEx > 80% of Operating Cash Flow | Computed ratios |
| Negative FCF | FCF < $0 | Computed FCF |
| Net Loss | Net Income < $0 | XBRL extracted |

All signals fire **deterministically** from computed facts — no LLM involvement.
            """)

        with st.expander("View raw signals.json"):
            st.json(sig)
