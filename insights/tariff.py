"""Simple tariff recommendation from usage pattern (peak vs off-peak share)."""
import pandas as pd


def tariff_recommendation(series: pd.Series) -> dict:
    """
    Compare peak (e.g. 7–9, 16–20) vs rest. If >~40% in peak, suggest
    considering a time-of-use tariff; else standard may be fine.
    """
    if series.empty or len(series) < 48 * 7:
        return {"recommendation": "Need at least a week of data.", "peak_share": None}

    peak_hours = [7, 8, 9, 16, 17, 18, 19, 20]
    s = series.copy()
    s.index = pd.to_datetime(s.index)
    peak_mask = s.index.hour.isin(peak_hours)
    peak_share = float(s[peak_mask].sum() / s.sum()) if s.sum() > 0 else 0

    if peak_share > 0.45:
        rec = "Consider a time-of-use tariff: a large share of use is in peak hours. Shifting some load could save money."
    elif peak_share > 0.35:
        rec = "Moderate peak usage. Compare single-rate vs time-of-use tariffs with your supplier."
    else:
        rec = "Usage is spread away from typical peak; standard single-rate may be fine. Still compare tariffs."

    return {"recommendation": rec, "peak_share": round(peak_share, 2)}


def _parse_hhmm(hhmm: str) -> int:
    """Convert 'HH:MM' to minutes-of-day."""
    s = str(hhmm).strip()
    hh, mm = s.split(":")
    return int(hh) * 60 + int(mm)


def _parse_window(window: str) -> tuple[int, int]:
    """
    Parse a window like '02:00-05:00' into (start_min, end_min).
    Supports windows that cross midnight (end < start).
    """
    w = window.strip()
    if "-" not in w:
        raise ValueError(f"Invalid tariff window: {window}. Expected 'HH:MM-HH:MM'.")
    left, right = w.split("-", 1)
    return _parse_hhmm(left), _parse_hhmm(right)


def _in_any_windows(minute_of_day: pd.Series, windows: list[str]) -> pd.Series:
    """Return boolean mask if minute_of_day falls into any provided window."""
    if not windows:
        return pd.Series(False, index=minute_of_day.index, dtype=bool)
    mask = pd.Series(False, index=minute_of_day.index, dtype=bool)
    for w in windows:
        start, end = _parse_window(w)
        if start < end:
            mask |= (minute_of_day >= start) & (minute_of_day < end)
        else:
            # Crosses midnight: e.g. 19:00-02:00
            mask |= (minute_of_day >= start) | (minute_of_day < end)
    return mask


def compute_elec_cost_gbp(
    series_kwh: pd.Series,
    *,
    standing_charge_p_per_day: float,
    base_rate_p_per_kwh: float,
    offpeak_rate_p_per_kwh: float,
    peak_rate_p_per_kwh: float,
    offpeak_windows: list[str] | None = None,
    peak_windows: list[str] | None = None,
) -> pd.Series:
    """
    Compute per-interval electricity cost in GBP from a kWh series and a time-of-use tariff.

    Tariff windows:
    - offpeak_windows: list like ['02:00-05:00']
    - peak_windows: list like ['16:00-19:00']
    - base: everything else (energy rate base_rate_p_per_kwh)

    Standing charge is allocated evenly across all intervals in a day based on the
    number of intervals present for that day in the series.
    """
    if series_kwh is None or series_kwh.empty:
        return pd.Series(dtype=float)

    s = series_kwh.copy()
    s.index = pd.to_datetime(s.index, utc=True, errors="coerce")
    s = s.dropna()
    if s.empty:
        return pd.Series(dtype=float)

    # Choose energy rate per interval using minute-of-day windows.
    if offpeak_windows is None:
        offpeak_windows = ["02:00-05:00"]
    if peak_windows is None:
        peak_windows = ["16:00-19:00"]

    minute_of_day = (s.index.hour * 60 + s.index.minute).astype(int)
    offpeak_mask = _in_any_windows(pd.Series(minute_of_day, index=s.index), offpeak_windows)
    peak_mask = _in_any_windows(pd.Series(minute_of_day, index=s.index), peak_windows)

    rate_p = pd.Series(float(base_rate_p_per_kwh), index=s.index, dtype=float)
    rate_p[offpeak_mask] = float(offpeak_rate_p_per_kwh)
    rate_p[peak_mask] = float(peak_rate_p_per_kwh)

    energy_cost_gbp = (s.astype(float) * rate_p) / 100.0

    # Allocate standing charge per day over the intervals present that day
    standing_gbp_per_day = float(standing_charge_p_per_day) / 100.0
    day = s.index.floor("D")
    counts = day.value_counts().to_dict()
    standing_per_interval = day.map(lambda d: standing_gbp_per_day / max(1, counts.get(d, 1)))
    standing_per_interval = pd.Series(standing_per_interval.values, index=s.index, dtype=float)

    return (energy_cost_gbp + standing_per_interval).rename("elec_cost_gbp")


def tariff_band_kwh_shares(
    series_kwh: pd.Series,
    *,
    offpeak_windows: list[str] | None = None,
    peak_windows: list[str] | None = None,
) -> dict:
    """
    Compute kWh shares for each tariff band based on provided windows.

    Returns:
    - peak_kwh, offpeak_kwh, base_kwh
    - peak_share, offpeak_share, base_share (fractions of total)
    """
    if series_kwh is None or series_kwh.empty:
        return {
            "peak_kwh": None,
            "offpeak_kwh": None,
            "base_kwh": None,
            "peak_share": None,
            "offpeak_share": None,
            "base_share": None,
        }

    s = series_kwh.copy()
    s.index = pd.to_datetime(s.index, utc=True, errors="coerce")
    s = s.dropna()
    if s.empty:
        return {
            "peak_kwh": None,
            "offpeak_kwh": None,
            "base_kwh": None,
            "peak_share": None,
            "offpeak_share": None,
            "base_share": None,
        }

    if offpeak_windows is None:
        offpeak_windows = ["02:00-05:00"]
    if peak_windows is None:
        peak_windows = ["16:00-19:00"]

    minute_of_day = (s.index.hour * 60 + s.index.minute).astype(int)
    offpeak_mask = _in_any_windows(pd.Series(minute_of_day, index=s.index), offpeak_windows)
    peak_mask = _in_any_windows(pd.Series(minute_of_day, index=s.index), peak_windows)
    base_mask = ~(offpeak_mask | peak_mask)

    offpeak_kwh = float(s[offpeak_mask].sum())
    peak_kwh = float(s[peak_mask].sum())
    base_kwh = float(s[base_mask].sum())
    total = peak_kwh + offpeak_kwh + base_kwh
    if total <= 0:
        return {
            "peak_kwh": peak_kwh,
            "offpeak_kwh": offpeak_kwh,
            "base_kwh": base_kwh,
            "peak_share": 0.0,
            "offpeak_share": 0.0,
            "base_share": 0.0,
        }

    return {
        "peak_kwh": peak_kwh,
        "offpeak_kwh": offpeak_kwh,
        "base_kwh": base_kwh,
        "peak_share": round(peak_kwh / total, 4),
        "offpeak_share": round(offpeak_kwh / total, 4),
        "base_share": round(base_kwh / total, 4),
    }


def tariff_cost_summary(cost_gbp: pd.Series) -> dict:
    """Summarise daily electricity cost (GBP)."""
    if cost_gbp is None or cost_gbp.empty:
        return {"message": "Not enough cost data.", "avg_daily_gbp": None, "total_gbp": None}
    s = cost_gbp.dropna().astype(float)
    if s.empty:
        return {"message": "Not enough cost data.", "avg_daily_gbp": None, "total_gbp": None}
    daily = s.resample("D").sum(min_count=1)
    total = float(daily.sum())
    avg = float(daily.mean())
    p90 = float(daily.quantile(0.9)) if len(daily) >= 3 else None
    msg = f"Electricity cost: avg £{avg:.2f}/day, total £{total:.2f}" + (f", p90 £{p90:.2f}/day." if p90 is not None else ".")
    return {"message": msg, "avg_daily_gbp": avg, "total_gbp": total, "p90_daily_gbp": p90}
