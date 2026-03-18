"""
Clean raw time-series CSVs to half-hourly: resample to 30T, drop duplicates, fill gaps.

Raw (mixed resolution): elec half-hourly, humidity minutely, internal_temp variable, weather hourly.
Output: data/cleaned/*.csv all at 30-min intervals, no duplicates, gaps filled appropriately.
"""
from pathlib import Path

import pandas as pd

from config import CLEANED_DIR, RAW_DIR

# Raw file names (in data/raw/)
RAW_ELECTRICITY = RAW_DIR / "electricity.csv"
RAW_HUMIDITY = RAW_DIR / "humidity.csv"
RAW_INTERNAL_TEMP = RAW_DIR / "internal_temp.csv"
RAW_WEATHER = RAW_DIR / "weather.csv"

FREQ = "30min"  # half-hourly (pandas: use "min" not "T")


def _load_series(path: Path, value_col: str, ts_col: str = None) -> pd.Series:
    """Load CSV to Series with datetime index; normalize column names."""
    if not path.exists():
        return pd.Series(dtype=float)
    df = pd.read_csv(path)
    ts_col = ts_col or next((c for c in ["timestamp", "date", "datetime", "time"] if c in df.columns), df.columns[0])
    if value_col not in df.columns:
        value_col = [c for c in df.columns if c != ts_col][0] if len(df.columns) > 1 else df.columns[0]
    df["ts"] = pd.to_datetime(df[ts_col], utc=True)
    df = df.drop_duplicates(subset=["ts"], keep="first").set_index("ts").sort_index()
    return df[value_col].astype(float)


def _load_weather(path: Path) -> pd.DataFrame:
    """Load weather CSV to DataFrame with datetime index; coerce numeric cols."""
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    ts_col = next((c for c in ["timestamp", "ts", "date", "datetime", "time"] if c in df.columns), df.columns[0])
    df["ts"] = pd.to_datetime(df[ts_col], utc=True)
    df = df.drop(columns=[ts_col], errors="ignore").drop_duplicates(subset=["ts"], keep="first").set_index("ts").sort_index()
    for c in df.select_dtypes(include=["object"]).columns:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def clean_elec(raw_path: Path = RAW_ELECTRICITY, out_path: Path = None) -> Path:
    """Resample to 30T (sum), dedupe, fill gaps with 0. Output: timestamp, kwh."""
    out_path = out_path or CLEANED_DIR / "electricity.csv"
    if not raw_path.exists():
        return out_path
    s = _load_series(raw_path, value_col="kwh")
    if s.empty:
        return out_path
    s = s[~s.index.duplicated(keep="first")]
    halfhourly = s.resample(FREQ).sum(min_count=1)
    halfhourly = halfhourly.fillna(0)
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    out = halfhourly.reset_index()
    out.columns = ["timestamp", "kwh"]
    out.to_csv(out_path, index=False)
    return out_path


def clean_humidity(raw_path: Path = RAW_HUMIDITY, out_path: Path = None) -> Path:
    """Resample to 30T (mean), dedupe, fill gaps with time interpolation then ffill/bfill."""
    out_path = out_path or CLEANED_DIR / "humidity.csv"
    s = _load_series(raw_path, value_col="humidity_percent")
    if s.empty:
        return out_path
    s = s[~s.index.duplicated(keep="first")]
    halfhourly = s.resample(FREQ).mean()
    halfhourly = halfhourly.interpolate(method="time").ffill().bfill()
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    out = halfhourly.reset_index()
    out.columns = ["timestamp", "humidity_percent"]
    out.to_csv(out_path, index=False)
    return out_path


def clean_internal_temp(raw_path: Path = RAW_INTERNAL_TEMP, out_path: Path = None) -> Path:
    """Resample to 30T (mean), dedupe, fill gaps with time interpolation then ffill/bfill."""
    out_path = out_path or CLEANED_DIR / "internal_temp.csv"
    s = _load_series(raw_path, value_col="temperature_celsius")
    if s.empty:
        return out_path
    s = s[~s.index.duplicated(keep="first")]
    halfhourly = s.resample(FREQ).mean()
    halfhourly = halfhourly.interpolate(method="time").ffill().bfill()
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    out = halfhourly.reset_index()
    out.columns = ["timestamp", "temperature_celsius"]
    out.to_csv(out_path, index=False)
    return out_path


def clean_weather(raw_path: Path = RAW_WEATHER, out_path: Path = None) -> Path:
    """Resample to 30T (mean), dedupe, fill gaps with ffill. Output: timestamp + weather cols only."""
    out_path = out_path or CLEANED_DIR / "weather.csv"
    df = _load_weather(raw_path)
    if df.empty:
        return out_path
    halfhourly = df.resample(FREQ).mean()
    halfhourly = halfhourly.ffill().bfill()
    CLEANED_DIR.mkdir(parents=True, exist_ok=True)
    out = halfhourly.reset_index()
    out = out.rename(columns={"ts": "timestamp"})
    out.to_csv(out_path, index=False)
    return out_path


def clean_all() -> dict:
    """Run all cleaners. Returns dict of name -> output path."""
    out = {}
    out["electricity"] = clean_elec()
    out["humidity"] = clean_humidity()
    out["internal_temp"] = clean_internal_temp()
    out["weather"] = clean_weather()
    return out
