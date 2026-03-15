"""Build an hourly-aggregated dataset from raw CSVs.

This keeps all aggregation logic in Python for now:
- Elec / gas: half-hourly -> hourly sum (energy per hour).
- Internal temp / humidity: minutely -> hourly mean.
- Weather: hourly (or finer) -> hourly mean.

Returns a tuple of:
- hourly_df: pandas.DataFrame indexed by hour.
- home_profile: pandas.DataFrame with static home features.
"""

from functools import reduce
from pathlib import Path
from typing import Tuple

import pandas as pd

from config import (
    ELECTRICITY_CSV,
    GAS_CSV,
    HUMIDITY_CSV,
    TEMPERATURE_CSV,
    WEATHER_CSV,
    HOME_PROFILE_CSV,
)
from data.loaders import (
    load_elec,
    load_gas,
    load_humidity,
    load_temperature,
    load_weather,
    load_home_profile,
)


def _resample_sum_hourly(series: pd.Series) -> pd.Series:
    """Resample a series to hourly using sum, preserving NaN for empty hours."""
    if series.empty:
        return series
    return series.resample("1h").sum(min_count=1)


def _resample_mean_hourly(series: pd.Series) -> pd.Series:
    """Resample a series to hourly using mean."""
    if series.empty:
        return series
    return series.resample("1h").mean()


def build_hourly_dataset(
    electricity_csv: Path = ELECTRICITY_CSV,
    gas_csv: Path = GAS_CSV,
    humidity_csv: Path = HUMIDITY_CSV,
    temperature_csv: Path = TEMPERATURE_CSV,
    weather_csv: Path = WEATHER_CSV,
    home_profile_csv: Path = HOME_PROFILE_CSV,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Aggregate all time-series data to hourly resolution and join into one frame.

    Columns in the returned hourly DataFrame:
    - elec_kwh
    - gas_kwh   (or m3, depending on source; name kept generic)
    - internal_temperature_c
    - internal_humidity_pct
    - plus weather columns if available.
    """
    # Load raw series
    elec = load_elec(electricity_csv)
    gas = load_gas(gas_csv)
    hum = load_humidity(humidity_csv)
    temp = load_temperature(temperature_csv)
    weather = load_weather(weather_csv)

    # Hourly aggregation
    elec_h = _resample_sum_hourly(elec)
    gas_h = _resample_sum_hourly(gas)
    hum_h = _resample_mean_hourly(hum)
    temp_h = _resample_mean_hourly(temp)

    if not weather.empty:
        weather_h = weather.resample("1h").mean()
    else:
        weather_h = weather

    # Build a unified hourly index from all pieces
    indexes = [
        s.index
        for s in [elec_h, gas_h, hum_h, temp_h]
        if hasattr(s, "index") and len(s) > 0
    ]
    if not weather_h.empty:
        indexes.append(weather_h.index)

    if not indexes:
        hourly_df = pd.DataFrame()
    else:
        all_index = reduce(lambda a, b: a.union(b), indexes)
        hourly_df = pd.DataFrame(index=all_index)

    if not elec_h.empty:
        hourly_df["elec_kwh"] = elec_h
    if not gas_h.empty:
        hourly_df["gas_kwh"] = gas_h
    if not temp_h.empty:
        hourly_df["internal_temperature_c"] = temp_h
    if not hum_h.empty:
        hourly_df["internal_humidity_pct"] = hum_h
    if not weather_h.empty:
        for col in weather_h.columns:
            hourly_df[col] = weather_h[col]

    # Load static home profile
    home_profile = load_home_profile(home_profile_csv)

    return hourly_df.sort_index(), home_profile

