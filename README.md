## GridLedger

**AI-native revenue intelligence for energy assets.**  
GridLedger turns live electricity price data into underwriting-style revenue snapshots for battery projects.

- **Repo**: `https://github.com/cbarry10/GridLedger`
- **Status**: Prototype v0.1 – single-node, single-asset revenue snapshot

---

## What GridLedger Does

GridLedger is a deterministic pipeline that:

1. **Ingests market data** (CAISO LMP for now).
2. **Cleans & normalizes** the dataset into a reproducible schema.
3. **Computes descriptive price metrics** (mean, range, volatility, etc.).
4. **Classifies risk** based on price volatility.
5. **Estimates simple battery revenue** using configurable assumptions.
6. **Generates an AI underwriting memo** grounded in those metrics.
7. **Writes structured outputs** (JSON, CSV, text) for future automation.

The goal: go from **raw prices → revenue & risk snapshot → investor-ready memo** in one command.

---

## Architecture

The pipeline is intentionally simple and modular:

- **Entry point**
  - `main.py` — orchestrates the full “AC1–AC6” flow.

- **Pipeline tasks**
  - `gridledger/tasks/ingestion.py`  
    `fetch_caiso_prices()`, `normalize_caiso_lmp()`
  - `gridledger/tasks/metrics.py`  
    `compute_price_metrics(df)` – AC2
  - `gridledger/tasks/risk.py`  
    `classify_volatility_risk(metrics)` – AC4
  - `gridledger/tasks/revenue.py`  
    `estimate_revenue(metrics, scenario)` – AC3
  - `gridledger/tasks/memo.py`  
    `generate_underwriting_memo(...)` – AC5
  - `gridledger/tasks/output.py`  
    `save_structured_outputs(...)` – AC6

- **Config & orchestration**
  - `gridledger/config/settings.py` — default dates, scenarios, output dirs.
  - `gridledger/run.py` — helper wrapper for agent/orchestrator (e.g. OpenClaw).

All steps are **deterministic**: the same inputs produce the same metrics, revenue, risk label, and memo.

---

## Quickstart

### 1. Clone and set up Python

git clone https://github.com/cbarry10/GridLedger.git
cd GridLedger

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
