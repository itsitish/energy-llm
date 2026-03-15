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
