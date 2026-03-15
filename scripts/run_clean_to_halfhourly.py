"""
Run clean_to_halfhourly: read raw CSVs from data/raw/, output half-hourly CSVs to data/cleaned/.
Run after placing electricity.csv, humidity.csv, internal_temp.csv, weather.csv in data/raw/.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.clean_to_halfhourly import clean_all

if __name__ == "__main__":
    paths = clean_all()
    for name, p in paths.items():
        if p.exists():
            n = sum(1 for _ in open(p)) - 1
            print(f"{name}: {n} rows -> {p}")
        else:
            print(f"{name}: no raw file, skipped")
