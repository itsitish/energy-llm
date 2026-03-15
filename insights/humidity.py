"""Internal humidity insights from a series (any resolution)."""
import pandas as pd


def humidity_summary(series: pd.Series) -> dict:
    """
    Summarise internal humidity series (e.g. from load_humidity).
    Returns dict with mean_pct, min_pct, max_pct and a short message.
    """
    if series.empty or len(series.dropna()) < 10:
        return {"mean_pct": None, "min_pct": None, "max_pct": None, "message": "Not enough humidity data."}
    s = series.dropna()
    mean_pct = float(s.mean())
    min_pct = float(s.min())
    max_pct = float(s.max())
    msg = f"Internal humidity: mean {mean_pct:.1f}%, range {min_pct:.1f}–{max_pct:.1f}%."
    return {"mean_pct": mean_pct, "min_pct": min_pct, "max_pct": max_pct, "message": msg}
