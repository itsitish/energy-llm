"""Paths and options. Raw (mixed resolution) in data/raw/; cleaned (half-hourly) in data/cleaned/."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
CLEANED_DIR = ROOT / "data" / "cleaned"
DATA_DIR = CLEANED_DIR

# Pipeline reads from cleaned (all half-hourly after run_clean_to_halfhourly)
ELECTRICITY_CSV = CLEANED_DIR / "electricity.csv"   # timestamp, kwh
GAS_CSV = CLEANED_DIR / "gas.csv"                   # timestamp, kwh
HUMIDITY_CSV = CLEANED_DIR / "humidity.csv"         # timestamp, humidity_percent
TEMPERATURE_CSV = CLEANED_DIR / "internal_temp.csv" # timestamp, temperature_celsius
WEATHER_CSV = CLEANED_DIR / "weather.csv"           # timestamp + weather columns

# Static home profile: cooking/heating/hot_water 1=elec 0=gas; evs/solar/heat_pump/battery 1=have 0=don't; elec_eac/gas_eac=est. annual consumption
HOME_PROFILE_CSV = CLEANED_DIR / "home_profile.csv"
# Backwards-compatible fallback if the cleaned file isn't present.
if not HOME_PROFILE_CSV.exists():
    HOME_PROFILE_CSV = RAW_DIR / "home_profile.csv"

# Tigerdata extraction: set TIGERDATA_URL + refs below; script runs data/sql/*.sql
TIGERDATA_URL = os.environ.get("TIGERDATA_URL", "")  # e.g. postgresql://user:pass@host/db
DEVICE_ID = os.environ.get("DEVICE_ID", "")          # fallback ref if refs below unset
TIGERDATA_REF_ELEC = os.environ.get("TIGERDATA_REF_ELEC", "")   # for elec.sql :itish_elec
TIGERDATA_REF_INT_TEMP = os.environ.get("TIGERDATA_REF_INT_TEMP", "")  # for internal_temperature.sql :itish_int_temp
TIGERDATA_REF_HUMIDITY = os.environ.get("TIGERDATA_REF_HUMIDITY", "")  # for humidity.sql if present
POSTCODE_DISTRICT = os.environ.get("POSTCODE_DISTRICT", "")    # for weather_observations.sql
