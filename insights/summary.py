"""
Aggregate household time-series into an LLM-friendly context block.

This module is intentionally "explainable": it uses simple descriptive stats,
seasonality summaries, and correlations (no ML) to create a compact narrative.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class SeriesCoverage:
    """Coverage metadata for a time-indexed series/dataframe."""

    start: pd.Timestamp | None
    end: pd.Timestamp | None
    points: int
    non_null_points: int

    @property
    def coverage_str(self) -> str:
        if self.start is None or self.end is None:
            return "no coverage"
        return f"{self.start} → {self.end} ({self.non_null_points}/{self.points} points)"


def _coverage(obj: pd.Series | pd.DataFrame) -> SeriesCoverage:
    """Compute coverage info; robust to empty input."""
    if obj is None or len(obj) == 0:
        return SeriesCoverage(None, None, 0, 0)
    idx = obj.index
    if not isinstance(idx, pd.DatetimeIndex):
        idx = pd.to_datetime(idx, errors="coerce")
    idx = idx[idx.notna()]
    if len(idx) == 0:
        return SeriesCoverage(None, None, int(len(obj)), 0)
    non_null = int(obj.dropna().shape[0]) if isinstance(obj, pd.Series) else int(obj.dropna(how="all").shape[0])
    return SeriesCoverage(pd.Timestamp(idx.min()), pd.Timestamp(idx.max()), int(len(obj)), non_null)


def _weekday_weekend_split(s: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Return weekday and weekend subsets (Mon-Fri vs Sat-Sun)."""
    if s.empty:
        return s, s
    idx = pd.to_datetime(s.index)
    mask_weekend = idx.dayofweek >= 5
    return s[~mask_weekend], s[mask_weekend]


def _corr(a: pd.Series, b: pd.Series) -> float | None:
    """Pearson correlation after aligning; returns None if insufficient data."""
    if a.empty or b.empty:
        return None
    df = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    if len(df) < 20:
        return None
    try:
        return float(df["a"].corr(df["b"]))
    except Exception:
        return None


def _pct_in_range(s: pd.Series, lo: float, hi: float) -> float | None:
    """Percent of non-null points in [lo, hi]."""
    if s.empty:
        return None
    x = s.dropna()
    if len(x) < 10:
        return None
    return float(((x >= lo) & (x <= hi)).mean())


def _format_pct(p: float | None) -> str:
    return "n/a" if p is None else f"{p*100:.0f}%"


def _top_hours(s: pd.Series, top_n: int = 3, *, lowest: bool = False) -> list[int]:
    """Top/bottom hours-of-day by mean usage."""
    if s.empty:
        return []
    df = s.dropna().to_frame("v")
    if len(df) < 48:
        return []
    by_hour = df.groupby(df.index.hour)["v"].mean()
    picked = by_hour.nsmallest(top_n) if lowest else by_hour.nlargest(top_n)
    return [int(h) for h in picked.index.tolist()]


def _safe_float(x) -> float | None:
    try:
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return None
        return float(x)
    except Exception:
        return None


def _weather_cols(df: pd.DataFrame) -> list[str]:
    if df is None or df.empty:
        return []
    return [c for c in df.columns if c not in ("timestamp", "ts")]


def _norm_yes_no(x: Any) -> bool | None:
    """Normalize common Yes/No-like values into bool."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip().lower()
    if s in {"yes", "y", "true", "1"}:
        return True
    if s in {"no", "n", "false", "0"}:
        return False
    return None


def _fuel_label(v: Any) -> str | None:
    """Map home-profile fuel values to 'electric' or 'gas'.

    Supports both legacy numeric encoding (1=electric, 0=gas) and string labels
    like 'elec' / 'gas' / 'electric' / 'e'.
    """
    if v is None or (isinstance(v, float) and pd.isna(v)):
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


def _get_home_value(home_profile: pd.DataFrame, col: str) -> Any:
    """Get a scalar value for a column (expects 1-row profile)."""
    if home_profile is None or home_profile.empty or col not in home_profile.columns:
        return None
    return home_profile[col].iloc[0]


def _home_profile_block(
    home_profile: pd.DataFrame,
    *,
    lowest_hours: list[int],
    tariff_config: dict[str, Any] | None = None,
) -> str:
    """Build a compact home-profile section for the LLM.

    If tariff_config is provided, also include cheapest time windows for flexible
    loads (EV charging and electric heating/hot-water).
    """
    if home_profile is None or home_profile.empty:
        return ""

    cooking = _fuel_label(_get_home_value(home_profile, "cooking_type_fuel"))
    heating = _fuel_label(_get_home_value(home_profile, "heating_type_fuel"))
    hot_water = _fuel_label(_get_home_value(home_profile, "hot_water_fuel"))

    evs = _norm_yes_no(_get_home_value(home_profile, "evs"))
    solar = _norm_yes_no(_get_home_value(home_profile, "solar_panels"))
    heat_pump = _norm_yes_no(_get_home_value(home_profile, "heat_pump"))
    battery = _norm_yes_no(_get_home_value(home_profile, "battery"))

    prop_type = _get_home_value(home_profile, "property_type")
    num_people = _get_home_value(home_profile, "num_people")
    num_bedrooms = _get_home_value(home_profile, "num_bedrooms")
    elec_eac = _get_home_value(home_profile, "elec_estimated_annual_consumption")
    gas_eac = _get_home_value(home_profile, "gas_estimated_annual_consumption")

    def _fmt_est(x: Any) -> str:
        try:
            return f"{float(x):.0f}"
        except Exception:
            return "n/a"

    lowest_str = ", ".join(str(h) for h in lowest_hours[:3]) if lowest_hours else "n/a"

    flex_lines: list[str] = []
    if heating == "electric" or hot_water == "electric":
        flex_lines.append(
            f"Heating/hot-water are electric; consider shifting to lowest-usage hours ({lowest_str}) when possible."
        )
    if evs is True:
        flex_lines.append(f"EVs are present; charging in lowest-usage hours ({lowest_str}) can reduce peak impact.")
    if heat_pump is True and heating == "electric":
        flex_lines.append("Heat pump presence suggests thermostat/scheduling strategies may help.")
    if battery is True:
        flex_lines.append("Battery presence suggests you may benefit from charging in low hours and using during high hours.")

    # Tariff-based scheduling tips (grounded: derived from your tariff windows)
    if tariff_config is not None:
        offpeak_windows = tariff_config.get("offpeak_windows") or ["02:00-05:00"]
        offpeak_rate = tariff_config.get("offpeak_rate_p_per_kwh", None)
        offpeak_rate_str = (
            f"{float(offpeak_rate):.2f}p/kWh" if offpeak_rate is not None else "off-peak rate"
        )
        cheap_windows_str = ", ".join(offpeak_windows)

        if evs is True:
            flex_lines.append(
                f"Cheapest charging windows (energy rate): off-peak ({cheap_windows_str}) at {offpeak_rate_str}; consider scheduling EV charging there."
            )
        if heating == "electric" or hot_water == "electric":
            flex_lines.append(
                f"Cheapest time to run electric heating/hot-water: off-peak ({cheap_windows_str}) at {offpeak_rate_str}; this also often aligns with your lowest-usage hours ({lowest_str})."
            )
        if solar is True:
            flex_lines.append(
                "You have solar panels; when possible, align EV charging and other flexible loads with daytime usage to maximize self-consumption."
            )

    flex_block = "\n".join([f"- {l}" for l in flex_lines]) if flex_lines else "- No device-based shifting signals found."

    return (
        "HOME DEVICE PROFILE (GROUND TRUTH)\n"
        f"- Property type: {prop_type}\n"
        f"- People / bedrooms: {num_people} / {num_bedrooms}\n"
        f"- Cooking fuel: {cooking}\n"
        f"- Heating fuel: {heating}\n"
        f"- Hot water fuel: {hot_water}\n"
        f"- EVs: {('yes' if evs else 'no') if evs is not None else 'n/a'}; Solar panels: {('yes' if solar else 'no') if solar is not None else 'n/a'}; Heat pump: {('yes' if heat_pump else 'no') if heat_pump is not None else 'n/a'}; Battery: {('yes' if battery else 'no') if battery is not None else 'n/a'}\n"
        f"- Estimated annual: electricity={_fmt_est(elec_eac)} kWh, gas={_fmt_est(gas_eac)} kWh\n\n"
        "LIKELY FLEX / SHAPING OPPORTUNITIES (BASED ON DEVICES + ELECTRICITY PATTERNS)\n"
        f"{flex_block}"
    )


def build_household_context(
    *,
    elec: pd.Series,
    internal_temp: pd.Series,
    internal_humidity: pd.Series,
    weather: pd.DataFrame,
    home_profile: pd.DataFrame | None = None,
    tariff_config: dict[str, Any] | None = None,
) -> str:
    """
    Build a compact, LLM-ready context from all available data.

    Inputs are expected to be half-hourly (but not required). Index should be datetime.
    `home_profile` is a static device/fuel profile (e.g. electric vs gas heating/hot-water),
    used to add grounded flex-load implications.

    `tariff_config` (optional) adds tariff band usage shares and an estimated electricity
    cost under the provided time-of-use rates.
    """
    # Coverage
    cov_elec = _coverage(elec)
    cov_t = _coverage(internal_temp)
    cov_h = _coverage(internal_humidity)
    cov_w = _coverage(weather)

    lines: list[str] = []
    lines.append("DATA COVERAGE")
    lines.append(f"- Electricity: {cov_elec.coverage_str}")
    lines.append(f"- Internal temperature: {cov_t.coverage_str}")
    lines.append(f"- Internal humidity: {cov_h.coverage_str}")
    lines.append(f"- Weather: {cov_w.coverage_str}")

    lowest_hours: list[int] = []

    # Electricity stats
    if not elec.empty and elec.dropna().shape[0] >= 48:
        s = elec.dropna().astype(float)
        daily = s.resample("D").sum(min_count=1)
        lines.append("")
        lines.append("ELECTRICITY PATTERNS")
        lines.append(f"- Typical daily usage: mean={daily.mean():.2f} kWh, p50={daily.median():.2f} kWh, p90={daily.quantile(0.9):.2f} kWh")
        lines.append(f"- Peak half-hour usage: {s.quantile(0.99):.2f} kWh (p99), max={s.max():.2f} kWh")
        lines.append(f"- Baseload estimate (p10 half-hour): {s.quantile(0.1):.2f} kWh")

        wk, we = _weekday_weekend_split(s)
        if not wk.empty and not we.empty:
            wk_daily = wk.resample("D").sum(min_count=1).mean()
            we_daily = we.resample("D").sum(min_count=1).mean()
            lines.append(f"- Weekday vs weekend avg daily usage: {wk_daily:.2f} vs {we_daily:.2f} kWh")

        peak_hours = _top_hours(s, top_n=3, lowest=False)
        low_hours = _top_hours(s, top_n=3, lowest=True)
        lowest_hours = low_hours
        if peak_hours:
            lines.append(f"- Highest-usage hours: {peak_hours} (hour-of-day)")
        if low_hours:
            lines.append(f"- Lowest-usage hours: {low_hours} (hour-of-day)")

    # Tariff impact (optional)
    if tariff_config is not None and elec is not None and not elec.empty:
        try:
            from insights.tariff import (
                compute_elec_cost_gbp,
                tariff_band_kwh_shares,
                tariff_cost_summary,
            )

            cost_series = compute_elec_cost_gbp(
                elec,
                standing_charge_p_per_day=float(tariff_config["standing_charge_p_per_day"]),
                base_rate_p_per_kwh=float(tariff_config["base_rate_p_per_kwh"]),
                offpeak_rate_p_per_kwh=float(tariff_config["offpeak_rate_p_per_kwh"]),
                peak_rate_p_per_kwh=float(tariff_config["peak_rate_p_per_kwh"]),
                offpeak_windows=tariff_config.get("offpeak_windows"),
                peak_windows=tariff_config.get("peak_windows"),
            )
            shares = tariff_band_kwh_shares(
                elec,
                offpeak_windows=tariff_config.get("offpeak_windows"),
                peak_windows=tariff_config.get("peak_windows"),
            )
            cost_summary = tariff_cost_summary(cost_series)

            lines.append("")
            lines.append("TARIFF SCHEDULE (YOUR RATES)")
            offpeak_windows = tariff_config.get("offpeak_windows") or ["02:00-05:00"]
            peak_windows = tariff_config.get("peak_windows") or ["16:00-19:00"]
            standing_charge_p_per_day = float(tariff_config["standing_charge_p_per_day"])
            base_rate_p_per_kwh = float(tariff_config["base_rate_p_per_kwh"])
            offpeak_rate_p_per_kwh = float(tariff_config["offpeak_rate_p_per_kwh"])
            peak_rate_p_per_kwh = float(tariff_config["peak_rate_p_per_kwh"])
            lines.append(f"- Standing charge: {standing_charge_p_per_day:.2f}p/day")
            lines.append(
                f"- Off-peak: {', '.join(offpeak_windows)} @ {offpeak_rate_p_per_kwh:.2f}p/kWh"
            )
            lines.append(
                f"- Peak: {', '.join(peak_windows)} @ {peak_rate_p_per_kwh:.2f}p/kWh"
            )
            lines.append(f"- Base: all other times @ {base_rate_p_per_kwh:.2f}p/kWh")
            lines.append(
                f"- Cheapest energy rate: off-peak @ {offpeak_rate_p_per_kwh:.2f}p/kWh"
            )
            lines.append("")
            lines.append("TARIFF IMPACT (YOUR RATES)")
            if shares.get("peak_share") is not None:
                lines.append(
                    "- Usage split (kWh share): "
                    f"peak={shares['peak_share']*100:.0f}%, "
                    f"off-peak={shares['offpeak_share']*100:.0f}%, "
                    f"base={shares['base_share']*100:.0f}%"
                )
            if cost_summary.get("avg_daily_gbp") is not None:
                lines.append(
                    f"- Estimated cost: {cost_summary.get('avg_daily_gbp'):.2f} GBP/day (avg), "
                    f"{cost_summary.get('total_gbp'):.2f} GBP total"
                )
        except Exception:
            # Don't fail context generation if tariff config is malformed.
            pass

    # Home profile implications (device fuels, EV/battery, plus optional tariff tips)
    hp_block = _home_profile_block(
        home_profile,
        lowest_hours=lowest_hours,
        tariff_config=tariff_config,
    )
    if hp_block:
        lines.append("")
        lines.append(hp_block)

    # Comfort stats
    if not internal_temp.empty or not internal_humidity.empty:
        lines.append("")
        lines.append("INDOOR COMFORT")
        if not internal_temp.empty:
            t = internal_temp.dropna().astype(float)
            if len(t) >= 10:
                lines.append(f"- Temp: mean={t.mean():.1f}°C, min={t.min():.1f}°C, max={t.max():.1f}°C, in 18–21°C: {_format_pct(_pct_in_range(t, 18.0, 21.0))}")
        if not internal_humidity.empty:
            h = internal_humidity.dropna().astype(float)
            if len(h) >= 10:
                lines.append(f"- Humidity: mean={h.mean():.1f}%, min={h.min():.1f}%, max={h.max():.1f}%, in 40–60%: {_format_pct(_pct_in_range(h, 40.0, 60.0))}")

    # Weather stats (keep brief, but include all available vars as ranges)
    if weather is not None and not weather.empty:
        wcols = _weather_cols(weather)
        lines.append("")
        lines.append("WEATHER (EXTERNAL)")
        # Summarise a few common fields explicitly if present
        if "temperature_celsius" in weather.columns:
            wt = pd.to_numeric(weather["temperature_celsius"], errors="coerce").dropna()
            if len(wt) >= 10:
                lines.append(f"- External temp: mean={wt.mean():.1f}°C, min={wt.min():.1f}°C, max={wt.max():.1f}°C")
        if "precipitation_mm" in weather.columns:
            pr = pd.to_numeric(weather["precipitation_mm"], errors="coerce").dropna()
            if len(pr) >= 10:
                wet_share = float((pr > 0).mean())
                lines.append(f"- Precipitation: {_safe_float(pr.sum()):.1f} mm total (non-zero on {_format_pct(wet_share)})")
        # Then add concise ranges for remaining variables
        extra_cols = [c for c in wcols if c not in ("temperature_celsius", "precipitation_mm")]
        if extra_cols:
            parts: list[str] = []
            for c in extra_cols:
                x = pd.to_numeric(weather[c], errors="coerce").dropna()
                if len(x) < 10:
                    continue
                parts.append(f"{c}: {x.min():.1f}–{x.max():.1f}")
            if parts:
                lines.append("- Other ranges: " + "; ".join(parts[:8]) + ("; ..." if len(parts) > 8 else ""))

    # Cross-signal correlations (helpful for LLM reasoning)
    lines.append("")
    lines.append("CROSS-SIGNAL RELATIONSHIPS (CORRELATIONS)")
    if not elec.empty and weather is not None and not weather.empty and "temperature_celsius" in weather.columns:
        ext = pd.to_numeric(weather["temperature_celsius"], errors="coerce")
        r = _corr(elec.astype(float), ext.astype(float))
        lines.append(f"- Elec vs external temp corr: {r:.2f}" if r is not None else "- Elec vs external temp corr: n/a")
    if not internal_temp.empty and weather is not None and not weather.empty and "temperature_celsius" in weather.columns:
        ext = pd.to_numeric(weather["temperature_celsius"], errors="coerce")
        r = _corr(internal_temp.astype(float), ext.astype(float))
        lines.append(f"- Internal vs external temp corr: {r:.2f}" if r is not None else "- Internal vs external temp corr: n/a")
    if not internal_temp.empty and not internal_humidity.empty:
        r = _corr(internal_temp.astype(float), internal_humidity.astype(float))
        lines.append(f"- Internal temp vs humidity corr: {r:.2f}" if r is not None else "- Internal temp vs humidity corr: n/a")

    return "\n".join(lines).strip()

