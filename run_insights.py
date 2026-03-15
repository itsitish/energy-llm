"""
Run insight pipeline: load your data, compute peaks, tariff rec, schedule suggestion.
Add your CSV paths in config.py. Without data, prints placeholder output.
"""
import sys
from pathlib import Path

# allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import ELECTRICITY_CSV, GAS_CSV
from data.loaders import load_elec, load_gas
from insights import peak_usage_times, tariff_recommendation, schedule_suggestion


def main():
    elec = load_elec(ELECTRICITY_CSV)
    gas = load_gas(GAS_CSV)

    # Prefer electricity for peak/tariff/schedule; gas for peaks only
    series = elec if not elec.empty else gas
    if series.empty:
        print("No data found. Put electricity.csv (and/or gas.csv) in data/raw/ with columns: timestamp, kwh")
        print("Example: timestamp,kwh\n2024-01-01 00:00:00,0.5\n2024-01-01 00:30:00,0.3\n...")
        return

    print("=== Peak usage times ===")
    print(peak_usage_times(series))

    print("\n=== Tariff recommendation ===")
    print(tariff_recommendation(series))

    print("\n=== Schedule suggestion ===")
    print(schedule_suggestion(series))


if __name__ == "__main__":
    main()
