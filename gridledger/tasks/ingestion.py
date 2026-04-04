# gridledger/tasks/ingestion.py
#
# Layer 1 — Data Ingestion
# Two responsibilities:
#   1. fetch_xbrl_facts()    — pull structured financials from SEC EDGAR XBRL API
#   2. fetch_10k_filing()    — download raw 10-K HTML for Item 1 context
#
# All CAISO/energy-trading code has been removed (Cortex v3).

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path

import requests

from gridledger.config.settings import (
    ANNUAL_PERIOD_MIN_DAYS,
    DOMINION_CIK,
    DOMINION_NAME,
    DOMINION_TICKER,
    EDGAR_BASE_URL,
    EDGAR_USER_AGENT,
    FILING_DIR,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# XBRL tag priority lists (first tag found with data wins)
# ---------------------------------------------------------------------------

_TAG_MAP: dict[str, list[str]] = {
    "revenue": [
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
    ],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
    ],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForCapitalImprovements",
    ],
    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss",
    ],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_xbrl_facts(cik: str = DOMINION_CIK) -> dict:
    """
    Fetch all XBRL company facts for a given CIK from SEC EDGAR.

    Returns a dict with keys: revenue, operating_cash_flow, capex, net_income.
    Each value is either {"value": <int>, "tag": <str>, "period": <str>}
    or {"value": None, "error": <str>}.
    """
    url = f"{EDGAR_BASE_URL}/CIK{cik}.json"
    logger.info("Fetching XBRL facts: %s", url)

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": EDGAR_USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.error("EDGAR XBRL request failed: %s", exc)
        return {k: {"value": None, "error": str(exc)} for k in _TAG_MAP}

    try:
        raw = resp.json()
    except ValueError as exc:
        logger.error("Failed to parse EDGAR JSON: %s", exc)
        return {k: {"value": None, "error": "JSON parse error"} for k in _TAG_MAP}

    facts = raw.get("facts", {})
    return {metric: _extract_latest_annual(facts, tags) for metric, tags in _TAG_MAP.items()}


def fetch_10k_filing(
    cik: str = DOMINION_CIK,
    ticker: str = DOMINION_TICKER,
    company_name: str = DOMINION_NAME,
) -> dict:
    """
    Download the latest 10-K filing HTML to disk (cached by today's date).

    Returns {"path": <str>, "cached": <bool>} or {"path": None, "error": <str>}.
    """
    today = date.today().isoformat()
    dest = FILING_DIR / f"{ticker}_10K_{today}.html"

    if dest.exists():
        logger.info("10-K filing already cached: %s", dest)
        return {"path": str(dest), "cached": True}

    logger.info("Downloading 10-K filing for %s (%s)…", company_name, ticker)

    try:
        from sec_edgar_downloader import Downloader  # lazy import — optional dep

        dl = Downloader(company_name, "contact@gridledger.ai", str(FILING_DIR))
        dl.get("10-K", ticker, limit=1)
    except Exception as exc:
        logger.error("sec-edgar-downloader failed: %s", exc)
        return {"path": None, "error": str(exc)}

    # sec-edgar-downloader nests files; find the first .htm / .html it wrote
    found = _find_downloaded_filing(ticker)
    if not found:
        return {"path": None, "error": "Filing downloaded but HTML file not located"}

    # Copy to our canonical path for easy date-based caching
    dest.write_bytes(found.read_bytes())
    logger.info("10-K saved to %s", dest)
    return {"path": str(dest), "cached": False}


def extract_item1_context(raw_doc_path: str, chars: int = 5000) -> str:
    """
    Strip HTML/SGML, find 'Item 1' anchor, return `chars` characters from that point.
    Falls back to 'Part I' anchor, then raw start of document.

    Handles both plain HTML files and sec-edgar-downloader full-submission.txt bundles.
    """
    from bs4 import BeautifulSoup

    raw = Path(raw_doc_path).read_text(encoding="utf-8", errors="ignore")

    # full-submission.txt is an SGML bundle — extract the largest <DOCUMENT> block
    # that contains actual HTML (identified by <html or <HTML tag inside)
    if raw_doc_path.endswith(".txt") and "<SEC-DOCUMENT>" in raw:
        raw = _extract_html_from_sgml_bundle(raw)

    text = BeautifulSoup(raw, "html.parser").get_text()

    lower = text.lower()
    anchor = lower.find("item 1")
    if anchor == -1:
        anchor = lower.find("part i")
    if anchor == -1:
        anchor = 0

    return text[anchor: anchor + chars]


def _extract_html_from_sgml_bundle(bundle: str) -> str:
    """
    EDGAR full-submission.txt bundles contain multiple <DOCUMENT> sections.
    Find the largest one that contains HTML — that's the 10-K body.
    """
    import re
    docs = re.findall(r"<DOCUMENT>(.*?)</DOCUMENT>", bundle, re.DOTALL)
    html_docs = [d for d in docs if "<html" in d.lower()]
    if not html_docs:
        return bundle  # fallback: parse whole thing
    # Return the largest HTML document block
    return max(html_docs, key=len)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_latest_annual(facts: dict, tags: list[str]) -> dict:
    """
    Try each tag in priority order.  Return the latest full-year 10-K value.
    """
    usgaap = facts.get("us-gaap", {})

    for tag in tags:
        if tag not in usgaap:
            continue

        units = usgaap[tag].get("units", {})
        usd_entries = units.get("USD", [])

        if not usd_entries:
            continue

        # Filter to full-year 10-K duration facts only
        annual = [
            e for e in usd_entries
            if e.get("form") == "10-K"
            and "start" in e  # duration fact (not point-in-time)
            and (
                datetime.fromisoformat(e["end"]) - datetime.fromisoformat(e["start"])
            ).days >= ANNUAL_PERIOD_MIN_DAYS
        ]

        if not annual:
            # Tag exists but no qualifying full-year entries — try next tag
            continue

        latest = sorted(annual, key=lambda e: e["end"], reverse=True)[0]
        return {
            "value": latest["val"],
            "tag": tag,
            "period": latest["end"],
        }

    # Exhausted all candidate tags
    return {
        "value": None,
        "error": f"No full-year 10-K entries found for tags {tags}",
    }


def _find_downloaded_filing(ticker: str) -> Path | None:
    """
    sec-edgar-downloader writes to sec-edgar-filings/<TICKER>/10-K/<accession>/
    Newer versions save full-submission.txt (SGML bundle); older saved .htm/.html.
    Walk FILING_DIR newest-first across all known extensions.
    """
    for pattern in [
        f"sec-edgar-filings/{ticker}/10-K/**/*.htm",
        f"sec-edgar-filings/{ticker}/10-K/**/*.html",
        f"sec-edgar-filings/{ticker}/10-K/**/full-submission.txt",
    ]:
        matches = sorted(
            FILING_DIR.glob(pattern),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if matches:
            return matches[0]
    return None
