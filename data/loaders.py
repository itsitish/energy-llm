"""Load half-hourly gas/elec from CSV. Expects timestamp + value column."""
from pathlib import Path
import pandas as pd


def load_hh_series(path: Path, value_col: str = "kwh") -> pd.Series:
    """
    Load half-hourly series from CSV.
    Expected columns: timestamp (or datetime), and one of kwh/value/m3.
    Returns Series index=datetime, values=usage.
    """
    if not path.exists():
        return pd.Series(dtype=float)

    df = pd.read_csv(path)
    # accept common column names
    ts_col = "timestamp" if "timestamp" in df.columns else "datetime"
    if ts_col not in df.columns and len(df.columns) >= 2:
        df = df.rename(columns={df.columns[0]: "timestamp", df.columns[1]: value_col})
        ts_col = "timestamp"
    elif ts_col not in df.columns:
        time_cols = [c for c in df.columns if "time" in c.lower() or c == "date"]
        ts_col = time_cols[0] if time_cols else df.columns[0]
    val_col = value_col if value_col in df.columns else "value"
    if val_col not in df.columns:
        val_col = df.columns[1]

    # Keep timestamps parseable across sources; upstream cleaning uses UTC.
    df["ts"] = pd.to_datetime(df[ts_col], errors="coerce", utc=True)
    df = df.set_index("ts").sort_index()
    return df[val_col].astype(float)


def load_elec(path: Path) -> pd.Series:
    """Load electricity half-hourly (kWh)."""
    return load_hh_series(path, value_col="kwh")


def load_gas(path: Path) -> pd.Series:
    """Load gas half-hourly (kWh or m3)."""
    return load_hh_series(path, value_col="kwh")


def load_humidity(path: Path) -> pd.Series:
    """Load humidity series (timestamp, humidity_percent)."""
    return load_hh_series(path, value_col="humidity_percent")


def load_temperature(path: Path) -> pd.Series:
    """Load temperature series (timestamp, temperature_celsius)."""
    return load_hh_series(path, value_col="temperature_celsius")


def load_weather(path: Path) -> pd.DataFrame:
    """
    Load external weather (hourly). Returns DataFrame with timestamp index
    and cols: temperature_celsius, humidity_percent, etc.
    Drops NaT and duplicate timestamps so resample/reindex work.
    """
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    ts_col = "timestamp" if "timestamp" in df.columns else "time"
    if ts_col not in df.columns:
        ts_col = df.columns[0]
    # Weather can arrive with mixed/invalid timestamps; coerce + drop NaT.
    df["ts"] = pd.to_datetime(df[ts_col], errors="coerce", utc=True)
    df = df.dropna(subset=["ts"]).drop_duplicates(subset=["ts"], keep="first")
    return df.set_index("ts").sort_index()


def load_home_profile(path: Path) -> pd.DataFrame:
    """
    Load static home profile (one row per home/device).
    Encoding: cooking_type, heating_type, hot_water: 1 = electric, 0 = gas.
    evs, solar, heat_pump, battery: 1 = have it, 0 = don't have.
    elec_eac, gas_eac = estimated annual consumption (kWh / units).
    """
    import pandas as pd

    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)
