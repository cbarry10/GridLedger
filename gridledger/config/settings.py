# gridledger/config/settings.py

from pathlib import Path
from datetime import date, timedelta

# -------------------------------------------------
# Project Paths
# -------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------------------------------
# CAISO API Settings
# -------------------------------------------------

CAISO_BASE_URL = "https://oasis.caiso.com/oasisapi/SingleZip"

# Default trading hub nodes
DEFAULT_NODES = [
    "TH_NP15_GEN-APND",
    "TH_SP15_GEN-APND",
    "TH_ZP26_GEN-APND",
]

# Default date range (last 7 days to keep payload small)
DEFAULT_END_DATE = date.today().isoformat()
DEFAULT_START_DATE = (date.today() - timedelta(days=7)).isoformat()

CAISO_TIMEZONE = "America/Los_Angeles"


# -------------------------------------------------
# Battery Modeling Defaults (AC3)
# -------------------------------------------------

# gridledger/config/settings.py

from pathlib import Path
from datetime import date, timedelta
import os
from dotenv import load_dotenv

# Load environment variables (.env)
load_dotenv()

# -------------------------------------------------
# Project Paths
# -------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

DATA_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# -------------------------------------------------
# CAISO API Settings
# -------------------------------------------------

CAISO_BASE_URL = "https://oasis.caiso.com/oasisapi/SingleZip"

# Default trading hub nodes
DEFAULT_NODES = [
    "TH_NP15_GEN-APND",
    "TH_SP15_GEN-APND",
    "TH_ZP26_GEN-APND",
]

# Default date range (last 7 days to keep payload small)
DEFAULT_END_DATE = date.today().isoformat()
DEFAULT_START_DATE = (date.today() - timedelta(days=7)).isoformat()

CAISO_TIMEZONE = "America/Los_Angeles"


# -------------------------------------------------
# Battery Modeling Defaults (AC3)
# -------------------------------------------------

DEFAULT_BATTERY_MWH = 2
DEFAULT_EFFICIENCY = 0.90
DEFAULT_CYCLES_PER_DAY = 1.0

SCENARIOS = {
    "conservative": {
        "battery_mwh": 2,
        "efficiency": 0.88,
        "cycles": 0.6,
    },
    "base": {
        "battery_mwh": 2,
        "efficiency": 0.90,
        "cycles": 1.0,
    },
    "aggressive": {
        "battery_mwh": 2,
        "efficiency": 0.92,
        "cycles": 1.5,
    },
}


# -------------------------------------------------
# Risk Classification Thresholds (AC4)
# Volatility measured as std deviation of hourly LMP
# -------------------------------------------------

LOW_VOL_THRESHOLD = 10
HIGH_VOL_THRESHOLD = 20


# -------------------------------------------------
# Claude Settings (AC5)
# -------------------------------------------------

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-opus-4-6"





