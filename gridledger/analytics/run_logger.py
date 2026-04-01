# gridledger/analytics/run_logger.py
import json
import getpass
import os
import uuid
from datetime import datetime
from pathlib import Path

from gridledger.config.settings import OUTPUT_DIR

RUN_LOG_PATH = OUTPUT_DIR / "run_log.jsonl"


def log_run(metrics: dict, revenue: dict, prompt_version: str, output_dir: str) -> str:
    """
    Appends one run record to outputs/run_log.jsonl.
    Returns the run_id for correlation with eval log.
    """
    run_id = str(uuid.uuid4())
    user = os.getenv("GRIDLEDGER_USER", getpass.getuser())

    record = {
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "user": user,
        "scenario": revenue.get("scenario"),
        "risk_level": metrics.get("risk_level"),
        "avg_price": metrics.get("average_price"),
        "volatility": metrics.get("volatility"),
        "simple_revenue": revenue.get("simple_revenue_estimate"),
        "arbitrage_revenue": revenue.get("arbitrage_proxy_revenue"),
        "prompt_version": prompt_version,
        "output_dir": str(output_dir),
    }

    with open(RUN_LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")

    return run_id


def load_run_history() -> list:
    """Returns all run records as a list of dicts."""
    if not RUN_LOG_PATH.exists():
        return []
    records = []
    with open(RUN_LOG_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records
