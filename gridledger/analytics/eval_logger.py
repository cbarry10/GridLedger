# gridledger/analytics/eval_logger.py
import json
from pathlib import Path

from gridledger.config.settings import OUTPUT_DIR

EVAL_LOG_PATH = OUTPUT_DIR / "eval_log.jsonl"


def log_eval(record: dict) -> None:
    """Appends one eval record to outputs/eval_log.jsonl."""
    with open(EVAL_LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")


def load_eval_history() -> list:
    """Returns all eval records as a list of dicts."""
    if not EVAL_LOG_PATH.exists():
        return []
    records = []
    with open(EVAL_LOG_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records
