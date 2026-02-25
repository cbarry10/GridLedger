import requests
import pandas as pd
import zipfile
import io

from gridledger.config.settings import (
    CAISO_BASE_URL,
    DEFAULT_NODES,
    DEFAULT_START_DATE,
    DEFAULT_END_DATE,
)


def fetch_caiso_prices(
    nodes=DEFAULT_NODES,
    start_date=DEFAULT_START_DATE,
    end_date=DEFAULT_END_DATE,
):
    """
    Fetch day-ahead LMP data from CAISO OASIS (PRC_LMP dataset).
    Returns raw dataframe.
    """

    # CAISO requires timestamps formatted like:
    # YYYYMMDDTHH:MM-0000
    start_str = start_date.replace("-", "") + "T08:00-0000"
    end_str = end_date.replace("-", "") + "T08:00-0000"

    params = {
        "queryname": "PRC_LMP",
        "version": "12",
        "market_run_id": "DAM",
        "resultformat": "6",  # CSV zipped
        "startdatetime": start_str,
        "enddatetime": end_str,
        "node": ",".join(nodes),
    }

    print("\n[AC1] Pulling CAISO DAM prices")
    print(f"Date range: {start_date} → {end_date}")

    response = requests.get(CAISO_BASE_URL, params=params)

    if response.status_code != 200:
        raise Exception(f"API request failed:\n{response.text}")

    # Unzip CAISO response
    z = zipfile.ZipFile(io.BytesIO(response.content))

    csv_files = [f for f in z.namelist() if f.endswith(".csv")]
    if not csv_files:
        raise Exception("No CSV file found in CAISO response")

    df = pd.read_csv(z.open(csv_files[0]))

    print(f"[AC1] Rows pulled: {len(df)}")

    return df


def normalize_caiso_lmp(df, nodes=None):
    """
    Convert raw CAISO LMP data into clean format:

    timestamp | node | lmp
    """

    clean = df[[
        "INTERVALSTARTTIME_GMT",
        "NODE_ID_XML",
        "MW"
    ]].copy()

    clean.rename(columns={
        "INTERVALSTARTTIME_GMT": "timestamp",
        "NODE_ID_XML": "node",
        "MW": "lmp"
    }, inplace=True)

    clean["timestamp"] = pd.to_datetime(clean["timestamp"])
    clean["lmp"] = pd.to_numeric(clean["lmp"], errors="coerce")

    # Optional node filtering
    if nodes:
        clean = clean[clean["node"].isin(nodes)]

    clean = clean.dropna(subset=["lmp"])
    clean = clean.sort_values("timestamp")

    return clean





