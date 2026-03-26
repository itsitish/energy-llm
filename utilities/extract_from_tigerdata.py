"""
Extract data from Tigerdata using SQL files in data/sql/; write raw CSVs to data/raw/.

Requires: TIGERDATA_URL (e.g. postgresql://user:pass@host/db).
Optional env: TIGERDATA_REF_ELEC, TIGERDATA_REF_INT_TEMP, TIGERDATA_REF_HUMIDITY, POSTCODE_DISTRICT.
Falls back to DEVICE_ID for refs when the specific ref env is unset.

Usage:
  TIGERDATA_URL=postgresql://... DEVICE_ID=your_ref python scripts/extract_from_tigerdata.py
  # Or set per-source refs:
  TIGERDATA_REF_ELEC=elec_ref TIGERDATA_REF_INT_TEMP=temp_ref POSTCODE_DISTRICT=AB1 python scripts/extract_from_tigerdata.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "data" / "sql"
sys.path.insert(0, str(ROOT))

from config import (
    RAW_DIR,
    TIGERDATA_URL,
    DEVICE_ID,
    TIGERDATA_REF_ELEC,
    TIGERDATA_REF_INT_TEMP,
    TIGERDATA_REF_HUMIDITY,
    POSTCODE_DISTRICT,
)

try:
    from sqlalchemy import create_engine, text
except ImportError:
    create_engine = text = None

import pandas as pd


def get_connection_url():
    """Tigerdata DB URL from env or config."""
    return os.environ.get("TIGERDATA_URL") or TIGERDATA_URL or None


def _run_sql(url: str, sql_path: Path, params: dict) -> pd.DataFrame:
    """Run SQL from file with bound params; return DataFrame."""
    if not url:
        raise RuntimeError("Set TIGERDATA_URL in config or env.")
    if create_engine is None or text is None:
        raise RuntimeError("pip install sqlalchemy psycopg2-binary")
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_path}")

    sql = sql_path.read_text()
    engine = create_engine(url)
    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        rows = result.fetchall()
        cols = list(result.keys())
    return pd.DataFrame(rows, columns=cols)


def extract_elec(out_path: Path = None) -> Path:
    """Run data/sql/elec.sql; write electricity.csv (timestamp, kwh) to data/raw/."""
    out_path = out_path or RAW_DIR / "electricity.csv"
    ref = TIGERDATA_REF_ELEC or DEVICE_ID
    if not ref:
        raise ValueError("Set TIGERDATA_REF_ELEC or DEVICE_ID for elec extraction.")

    df = _run_sql(get_connection_url(), SQL_DIR / "elec.sql", {"itish_elec": ref})
    # Pipeline expects timestamp, kwh; ensure order
    if "timestamp" in df.columns and "kwh" in df.columns:
        df = df[["timestamp", "kwh"]]
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return out_path


def extract_internal_temperature(out_path: Path = None) -> Path:
    """Run data/sql/internal_temperature.sql; write internal_temp.csv to data/raw/."""
    out_path = out_path or RAW_DIR / "internal_temp.csv"
    ref = TIGERDATA_REF_INT_TEMP or DEVICE_ID
    if not ref:
        raise ValueError("Set TIGERDATA_REF_INT_TEMP or DEVICE_ID for temperature extraction.")

    df = _run_sql(get_connection_url(), SQL_DIR / "internal_temperature.sql", {"itish_int_temp": ref})
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return out_path


def extract_humidity(out_path: Path = None) -> Path:
    """Run data/sql/humidity.sql if present; write humidity.csv to data/raw/."""
    out_path = out_path or RAW_DIR / "humidity.csv"
    sql_path = SQL_DIR / "humidity.sql"
    if not sql_path.exists():
        raise FileNotFoundError(f"No {sql_path}; add SQL or skip humidity.")
    ref = TIGERDATA_REF_HUMIDITY or DEVICE_ID
    if not ref:
        raise ValueError("Set TIGERDATA_REF_HUMIDITY or DEVICE_ID for humidity extraction.")

    # Use same param name as other SQLs; if your humidity.sql uses :device_id, add a branch or edit here
    params = {"itish_humidity": ref}
    df = _run_sql(get_connection_url(), sql_path, params)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return out_path


def extract_weather(out_path: Path = None) -> Path:
    """Run data/sql/weather_observations.sql; write weather.csv to data/raw/."""
    out_path = out_path or RAW_DIR / "weather.csv"
    district = POSTCODE_DISTRICT
    if not district:
        raise ValueError("Set POSTCODE_DISTRICT for weather extraction.")

    df = _run_sql(get_connection_url(), SQL_DIR / "weather_observations.sql", {"postcode_district": district})
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return out_path


def main():
    url = get_connection_url()
    if not url:
        print("Set TIGERDATA_URL (and refs). Example:")
        print("  TIGERDATA_URL=postgresql://user:pass@host/db DEVICE_ID=ref python scripts/extract_from_tigerdata.py")
        sys.exit(1)

    written = []
    # Elec
    try:
        p = extract_elec()
        n = sum(1 for _ in open(p)) - 1
        written.append(("electricity", p, n))
    except Exception as e:
        print(f"Elec: {e}")
    # Internal temp
    try:
        p = extract_internal_temperature()
        n = sum(1 for _ in open(p)) - 1
        written.append(("internal_temp", p, n))
    except Exception as e:
        print(f"Temperature: {e}")
    # Humidity (optional if no humidity.sql)
    try:
        p = extract_humidity()
        n = sum(1 for _ in open(p)) - 1
        written.append(("humidity", p, n))
    except (FileNotFoundError, ValueError) as e:
        print(f"Humidity: skipped ({e})")
    except Exception as e:
        print(f"Humidity: {e}")
    # Weather (optional if no POSTCODE_DISTRICT)
    if POSTCODE_DISTRICT:
        try:
            p = extract_weather()
            n = sum(1 for _ in open(p)) - 1
            written.append(("weather", p, n))
        except Exception as e:
            print(f"Weather: {e}")
    else:
        print("Weather: skipped (set POSTCODE_DISTRICT to extract)")

    for name, path, n in written:
        print(f"{name}: {n} rows -> {path}")


if __name__ == "__main__":
    main()
