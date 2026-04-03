# gridledger/analytics/run_logger.py
#
# Cortex v3 — Interface changed to log_run(record: dict)
# to match eval_logger pattern and support Cortex analytics fields.

import getpass
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from gridledger.config.settings import OUTPUT_DIR

RUN_LOG_PATH = OUTPUT_DIR / "run_log.jsonl"


def log_run(record: dict) -> str:
    """
    Append one run record to outputs/run_log.jsonl.

    The caller provides all fields as a dict.  This function enriches with
    run_id, timestamp, and user if not already present, then appends.

    Returns the run_id for correlation with eval_log.jsonl.

    Minimal required fields (caller should populate):
        prompt_version, output_dir, ticker, reporting_period,
        revenue, net_income, operating_cash_flow, capex, fcf, fcf_margin,
        signal_count, memo_word_count, composite_score
    """
    run_id = record.get("run_id") or str(uuid.uuid4())
    record.setdefault("run_id", run_id)
    record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    record.setdefault("user", os.getenv("GRIDLEDGER_USER", getpass.getuser()))

    RUN_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RUN_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    return run_id


def load_run_history() -> list:
    """Returns all run records as a list of dicts."""
    if not RUN_LOG_PATH.exists():
        return []
    records = []
    with open(RUN_LOG_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records
