"""Simple schedule suggestions: shift flexible load to cheaper hours."""
import pandas as pd


def schedule_suggestion(series: pd.Series) -> dict:
    """
    Suggest moving flexible use (e.g. washing, EV) to lower-usage hours.
    Uses average half-hour profile to find cheapest windows.
    """
    if series.empty or len(series) < 48 * 7:
        return {"message": "Need at least a week of data.", "best_hours": []}

    by_slot = series.groupby([series.index.hour, series.index.minute]).mean()
    # flatten to half-hour index 0..47
    by_slot.index = by_slot.index.get_level_values(0) * 2 + (
        by_slot.index.get_level_values(1) // 30
    )
    lowest = by_slot.nsmallest(6).index.tolist()
    # convert slot index back to hour
    best_hours = [int(s // 2) for s in lowest]

    return {
        "best_hours": sorted(set(best_hours)),
        "message": "Consider running washing machine, dishwasher, or EV charging in these hours when usage is typically lower.",
    }
