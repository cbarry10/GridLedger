# gridledger/config/settings.py

from pathlib import Path
import os
from dotenv import load_dotenv

# Load .env from the project root explicitly (prevents picking up a parent .env)
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=True)

# -------------------------------------------------
# Project Paths
# -------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
FILING_DIR = DATA_DIR / "filings"

DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
FILING_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------------------------------
# SEC EDGAR Settings
# -------------------------------------------------

DOMINION_CIK = "0000715957"
DOMINION_TICKER = "D"
DOMINION_NAME = "Dominion Energy"

EDGAR_BASE_URL = "https://data.sec.gov/api/xbrl/companyfacts"
EDGAR_USER_AGENT = "GridLedger/1.0 (contact@gridledger.ai)"

# Minimum days for a full-year 10-K period (guards against transition filings)
ANNUAL_PERIOD_MIN_DAYS = 350


# -------------------------------------------------
# FCF Signal Thresholds
# -------------------------------------------------

FCF_MARGIN_WARN_THRESHOLD = 0.05       # < 5% → capital pressure signal
CAPEX_TO_OCF_WARN_THRESHOLD = 0.80    # > 80% → high CapEx signal


# -------------------------------------------------
# Claude Settings
# -------------------------------------------------

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-opus-4-6"
