"""Monthly, annual, normals and trend tables from one city's daily frame.

Input daily frame columns: date, tmean_c, tmin_c, tmax_c, precip_mm and optionally
wind_mean_kmh, wind_max_kmh, solar_kwh_m2 (outputs derived from absent columns are
left out). Pure pandas/numpy, no I/O.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WET_MM = 1.0
HEAVY_MM = 20.0
BASE = (1991, 2020)


def _prep(daily: pd.DataFrame) -> pd.DataFrame:
    d = daily.copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.drop_duplicates("date").sort_values("date")
    d["year"] = d["date"].dt.year
    d["month"] = d["date"].dt.month
    return d


def _complete_months(d: pd.DataFrame) -> pd.DataFrame:
    n = d.groupby(["year", "month"])["date"].transform("count")
    return d[n == d["date"].dt.days_in_month]


def _complete_years(d: pd.DataFrame) -> pd.DataFrame:
    n = d.groupby("year")["date"].transform("count")
    leap = d["date"].dt.is_leap_year
    return d[n == np.where(leap, 366, 365)]


def _dd(d: pd.DataFrame) -> pd.DataFrame:
    t = d["tmean_c"]
    return pd.DataFrame({
        "hdd_15_5": (15.5 - t).clip(lower=0),
        "hdd_18": (18.0 - t).clip(lower=0),
        "cdd_18": (t - 18.0).clip(lower=0),
        "cdd_22": (t - 22.0).clip(lower=0),
        "gtz_20_15": np.where(t < 15.0, 20.0 - t, 0.0),
    }, index=d.index)


def monthly(daily: pd.DataFrame) -> pd.DataFrame:
    """One row per (year, month) for complete months only."""
    d = _complete_months(_prep(daily))
    d = pd.concat([d, _dd(d)], axis=1)
    d["_wet"] = d["precip_mm"] >= WET_MM
    d["_frost"] = d["tmin_c"] < 0
    agg = {
        "tmean_c": ("tmean_c", "mean"),
        "tmin_mean_c": ("tmin_c", "mean"),
        "tmax_mean_c": ("tmax_c", "mean"),
        "tmin_abs_c": ("tmin_c", "min"),
        "tmax_abs_c": ("tmax_c", "max"),
        "precip_mm": ("precip_mm", "sum"),
        "wet_days": ("_wet", "sum"),
        "frost_days": ("_frost", "sum"),
        "hdd_15_5": ("hdd_15_5", "sum"),
        "hdd_18": ("hdd_18", "sum"),
        "cdd_18": ("cdd_18", "sum"),
        "cdd_22": ("cdd_22", "sum"),
        "gtz_20_15": ("gtz_20_15", "sum"),
    }
    if "solar_kwh_m2" in d:
        agg["solar_kwh_m2"] = ("solar_kwh_m2", "sum")
    if "wind_mean_kmh" in d:
        agg["wind_mean_kmh"] = ("wind_mean_kmh", "mean")
    m = d.groupby(["year", "month"], as_index=False).agg(**agg)
    for c in ("wet_days", "frost_days"):
        m[c] = m[c].astype(int)
    return m.round(1)


def annual(daily: pd.DataFrame, base: tuple[int, int] = BASE) -> pd.DataFrame:
    """One row per complete calendar year with anomalies vs the base period."""
    d = _complete_years(_prep(daily))
    d = pd.concat([d, _dd(d)], axis=1)
    p, tn, tx = d["precip_mm"], d["tmin_c"], d["tmax_c"]
    d["_wet"] = p >= WET_MM
    d["_heavy"] = p >= HEAVY_MM
    d["_frost"] = tn < 0
    d["_ice"] = tx < 0
    d["_summer"] = tx >= 25
    d["_hot"] = tx >= 30
    d["_trop"] = tn >= 20
    a = d.groupby("year", as_index=False).agg(
        tmean_c=("tmean_c", "mean"),
        precip_mm=("precip_mm", "sum"),
        wet_days=("_wet", "sum"),
        heavy_rain_days=("_heavy", "sum"),
        max_1day_precip_mm=("precip_mm", "max"),
        frost_days=("_frost", "sum"),
        ice_days=("_ice", "sum"),
        summer_days=("_summer", "sum"),
        hot_days=("_hot", "sum"),
        tropical_nights=("_trop", "sum"),
        tmax_abs_c=("tmax_c", "max"),
        tmin_abs_c=("tmin_c", "min"),
        hdd_15_5=("hdd_15_5", "sum"),
        hdd_18=("hdd_18", "sum"),
        cdd_18=("cdd_18", "sum"),
        cdd_22=("cdd_22", "sum"),
    )
    inbase = a["year"].between(*base)
    t_base = a.loc[inbase, "tmean_c"].mean() if inbase.any() else np.nan
    p_base = a.loc[inbase, "precip_mm"].mean() if inbase.any() else np.nan
    a.insert(2, "tmean_anomaly_c", a["tmean_c"] - t_base)
    pct = (a["precip_mm"] / p_base - 1.0) * 100.0 if p_base else np.nan
    a.insert(4, "precip_anomaly_pct", pct)
    a["rank_warmest"] = a["tmean_c"].rank(ascending=False, method="min").astype(int)
    for c in ("wet_days", "heavy_rain_days", "frost_days", "ice_days",
              "summer_days", "hot_days", "tropical_nights"):
        a[c] = a[c].astype(int)
    return a.round(1)


def normals(monthly_df: pd.DataFrame, daily: pd.DataFrame | None = None,
            period: tuple[int, int] = BASE) -> pd.DataFrame:
    """12 rows of period means. summer_days/hot_days need the daily frame."""
    m = monthly_df[monthly_df["year"].between(*period)].copy()
    cols = {
        "tmean_c": "tmean_c", "tmin_c": "tmin_mean_c", "tmax_c": "tmax_mean_c",
        "precip_mm": "precip_mm", "wet_days": "wet_days", "frost_days": "frost_days",
    }
    out = pd.DataFrame({"month": range(1, 13)})
    g = m.groupby("month")
    for name, src in cols.items():
        out[name] = out["month"].map(g[src].mean())
    if daily is not None:
        d = _complete_months(_prep(daily))
        d = d[d["year"].between(*period)]
        d["_summer"] = d["tmax_c"] >= 25
        d["_hot"] = d["tmax_c"] >= 30
        ym = d.groupby(["year", "month"])[["_summer", "_hot"]].sum().groupby("month").mean()
        out["summer_days"] = out["month"].map(ym["_summer"])
        out["hot_days"] = out["month"].map(ym["_hot"])
    if "solar_kwh_m2" in m:
        days = pd.to_datetime(dict(year=m["year"], month=m["month"], day=1)).dt.days_in_month
        m["_solar_day"] = m["solar_kwh_m2"] / days
        out["solar_kwh_m2_day"] = out["month"].map(m.groupby("month")["_solar_day"].mean())
    if "wind_mean_kmh" in m:
        out["wind_mean_kmh"] = out["month"].map(g["wind_mean_kmh"].mean())
    for c in ("hdd_15_5", "hdd_18", "cdd_18"):
        out[c] = out["month"].map(g[c].mean())
    return out.round(1)


def _trend(a: pd.DataFrame, y0: int, y1: int) -> float | None:
    s = a[a["year"].between(y0, y1)].dropna(subset=["tmean_c"])
    if len(s) < 10:
        return None
    slope = np.polyfit(s["year"].astype(float), s["tmean_c"].astype(float), 1)[0]
    return round(float(slope) * 10.0, 2)


def summary(annual_df: pd.DataFrame, base: tuple[int, int] = BASE) -> dict:
    """Per-city trend columns for <cc>_cities.csv.

    Trends use annual_df tmean_c (1-decimal rounded values from annual()); a period
    with fewer than 10 years gives None.
    """
    a = annual_df
    b = a[a["year"].between(*base)]

    def _mean(c):
        return round(float(b[c].mean()), 1) if len(b) else None

    def _year(c, largest):
        if not len(a):
            return None
        i = a[c].idxmax() if largest else a[c].idxmin()
        return int(a.loc[i, "year"])

    return {
        "tmean_annual_c": _mean("tmean_c"),
        "precip_annual_mm": _mean("precip_mm"),
        "trend_c_per_decade_1951_2025": _trend(a, 1951, 2025),
        "trend_c_per_decade_1981_2025": _trend(a, 1981, 2025),
        "warmest_year": _year("tmean_c", True),
        "coldest_year": _year("tmean_c", False),
        "wettest_year": _year("precip_mm", True),
        "driest_year": _year("precip_mm", False),
    }
