"""Peak usage time insights from half-hourly series."""
import pandas as pd


def peak_usage_times(series: pd.Series, top_n: int = 5) -> dict:
    """
    Identify peak usage half-hours (by hour-of-day and day-of-week).
    series: index=datetime, value=usage (kWh).
    Returns dict with peak hours and weekday/weekend split.
    """
    if series.empty or len(series) < 48:
        return {"peak_hours": [], "peak_days": [], "message": "Not enough data."}

    df = series.to_frame("usage")
    df["hour"] = df.index.hour
    df["dayofweek"] = df.index.dayofweek  # 0=Mon, 6=Sun

    by_hour = df.groupby("hour")["usage"].mean()
    peak_hours = by_hour.nlargest(top_n).index.tolist()

    by_day = df.groupby("dayofweek")["usage"].mean()
    peak_days = by_day.nlargest(3).index.tolist()
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    peak_day_names = [day_names[i] for i in peak_days]

    return {
        "peak_hours": [int(h) for h in peak_hours],
        "peak_days": peak_day_names,
        "avg_daily_total": float(series.resample("D").sum().mean()),
    }
