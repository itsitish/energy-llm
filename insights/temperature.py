"""Internal temperature insights from a series (any resolution)."""
import pandas as pd


def temperature_summary(series: pd.Series) -> dict:
    """
    Summarise internal temperature series (e.g. from load_temperature).
    Returns dict with mean_c, min_c, max_c and a short message.
    """
    if series.empty or len(series.dropna()) < 10:
        return {"mean_c": None, "min_c": None, "max_c": None, "message": "Not enough temperature data."}
    s = series.dropna()
    mean_c = float(s.mean())
    min_c = float(s.min())
    max_c = float(s.max())
    msg = f"Internal temperature: mean {mean_c:.1f}°C, range {min_c:.1f}–{max_c:.1f}°C."
    return {"mean_c": mean_c, "min_c": min_c, "max_c": max_c, "message": msg}
