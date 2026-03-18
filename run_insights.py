"""
Run insight pipeline: load your data, compute peaks/tariff/schedule + home-profile implications.
Add your CSV paths in config.py. Without data, prints placeholder output.
"""
import sys
from pathlib import Path

# allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import ELECTRICITY_CSV, GAS_CSV, HOME_PROFILE_CSV
from data.loaders import load_elec, load_gas, load_home_profile
from insights import peak_usage_times, tariff_recommendation, schedule_suggestion


def _norm_yes_no(x) -> bool | None:
    """Normalize common Yes/No-like values into bool."""
    if x is None:
        return None
    s = str(x).strip().lower()
    if s in {"yes", "y", "true", "1"}:
        return True
    if s in {"no", "n", "false", "0"}:
        return False
    return None


def _fuel_label(v) -> str | None:
    """Map home-profile fuel values to 'electric' or 'gas'.

    Supports both legacy numeric encoding (1=electric, 0=gas) and string labels
    like 'elec' / 'gas' / 'electric' / 'e'.
    """
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"elec", "electric", "electricity", "e"}:
            return "electric"
        if s in {"gas", "natural gas", "g"}:
            return "gas"
    try:
        iv = int(float(v))
    except Exception:
        return None
    if iv == 1:
        return "electric"
    if iv == 0:
        return "gas"
    return None


def _lowest_usage_hours(series, top_n: int = 3) -> list[int]:
    """Find the lowest-usage hours-of-day by mean usage."""
    if series is None or getattr(series, "empty", True):
        return []
    s = series.dropna()
    if len(s) < 48:
        return []
    df = s.to_frame("v")
    by_hour = df.groupby(df.index.hour)["v"].mean()
    return [int(h) for h in by_hour.nsmallest(top_n).index.tolist()]


def main():
    elec = load_elec(ELECTRICITY_CSV)
    gas = load_gas(GAS_CSV)
    home_profile = load_home_profile(HOME_PROFILE_CSV)

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

    print("\n=== Home device profile (electric vs gas) ===")
    if home_profile.empty:
        print("(no home_profile.csv found)")
    else:
        cooking = _fuel_label(home_profile.get("cooking_type_fuel", [None]).iloc[0] if "cooking_type_fuel" in home_profile.columns else None)
        heating = _fuel_label(home_profile.get("heating_type_fuel", [None]).iloc[0] if "heating_type_fuel" in home_profile.columns else None)
        hot_water = _fuel_label(home_profile.get("hot_water_fuel", [None]).iloc[0] if "hot_water_fuel" in home_profile.columns else None)
        evs = _norm_yes_no(home_profile.get("evs", [None]).iloc[0] if "evs" in home_profile.columns else None)
        heat_pump = _norm_yes_no(home_profile.get("heat_pump", [None]).iloc[0] if "heat_pump" in home_profile.columns else None)
        battery = _norm_yes_no(home_profile.get("battery", [None]).iloc[0] if "battery" in home_profile.columns else None)

        lowest_hours = _lowest_usage_hours(elec)
        lowest_str = ", ".join(str(h) for h in lowest_hours) if lowest_hours else "n/a"

        print(f"- Cooking fuel: {cooking}; Heating fuel: {heating}; Hot-water fuel: {hot_water}")
        print(f"- EVs: {('yes' if evs else 'no') if evs is not None else 'n/a'}; Heat pump: {('yes' if heat_pump else 'no') if heat_pump is not None else 'n/a'}; Battery: {('yes' if battery else 'no') if battery is not None else 'n/a'}")
        if (heating == "electric" or hot_water == "electric") and lowest_hours:
            print(f"- Tip: shift heating/hot-water to lowest-usage hours ({lowest_str}) when possible.")
        if evs is True and lowest_hours:
            print(f"- Tip: charge EV in lowest-usage hours ({lowest_str}) when possible.")


if __name__ == "__main__":
    main()
