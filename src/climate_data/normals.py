"""Monthly and daily climate normals from ERA5 / ERA5-Land arrays (pure functions)."""
from __future__ import annotations

import calendar

import numpy as np
import xarray as xr

KELVIN = 273.15


def _time_name(obj) -> str:
    for name in ("time", "valid_time"):
        if name in obj.dims:
            return name
    raise ValueError("input has no 'time' or 'valid_time' dimension")


def _select_years(obj, start: int, end: int, daily: bool = False):
    """Restrict to years start..end; raise unless every month (every day if daily) is present."""
    if start > end:
        raise ValueError(f"start {start} > end {end}")
    t = _time_name(obj)
    years = obj[t].dt.year
    sel = obj.isel({t: ((years >= start) & (years <= end)).values})
    yrs = sel[t].dt.year.values
    mons = sel[t].dt.month.values
    have = set(zip(yrs.tolist(), mons.tolist()))
    missing = [(y, m) for y in range(start, end + 1) for m in range(1, 13) if (y, m) not in have]
    if missing:
        raise ValueError(f"incomplete period {start}-{end}: {len(missing)} missing months, first {missing[:3]}")
    if daily:
        days = sel[t].dt.floor("D").values
        n_unique = len(np.unique(days))
        expected = sum(366 if calendar.isleap(y) else 365 for y in range(start, end + 1))
        if n_unique != expected:
            raise ValueError(f"incomplete daily period {start}-{end}: {n_unique} of {expected} days")
    else:
        if len(yrs) != len(have):
            raise ValueError("duplicate monthly time steps")
    return sel, t


def monthly_normals(ds: xr.Dataset, start: int, end: int) -> xr.Dataset:
    """Monthly normals: tmean_c (t2m K -> degC) and precip_mm (tp mean daily rate m/day -> monthly total mm)."""
    sel, t = _select_years(ds, start, end)
    years = sel[t].dt.year.values
    months = sel[t].dt.month.values
    ndays = xr.DataArray(
        np.array([calendar.monthrange(int(y), int(m))[1] for y, m in zip(years, months)], dtype="float64"),
        dims=[t],
        coords={t: sel[t]},
    )
    tmean = (sel["t2m"] - KELVIN).groupby(f"{t}.month").mean(t)
    precip = (sel["tp"] * ndays * 1000.0).groupby(f"{t}.month").mean(t)
    out = xr.Dataset({"tmean_c": tmean, "precip_mm": precip})
    return out.drop_vars([v for v in ("number", "expver") if v in out.coords])


def daily_normals(tmax: xr.DataArray, tmin: xr.DataArray, start: int, end: int) -> xr.Dataset:
    """Daily-derived monthly normals: tmax_c, tmin_c, frost_days (tmin<0 degC), summer_days (tmax>=25 degC)."""
    tx, t = _select_years(tmax, start, end, daily=True)
    tn, t2 = _select_years(tmin, start, end, daily=True)
    tx_c = tx - KELVIN
    tn_c = tn - KELVIN

    def count_mean(cond: xr.DataArray, valid: xr.DataArray, tname: str) -> xr.DataArray:
        c = cond.where(valid).astype("float64")
        key = c[tname].dt.year * 100 + c[tname].dt.month
        c = c.assign_coords(ym=(tname, key.values))
        per = c.groupby("ym").sum(tname, min_count=1)
        per = per.assign_coords(month=("ym", (per["ym"].values % 100).astype(int)))
        return per.groupby("month").mean("ym")

    out = xr.Dataset(
        {
            "tmax_c": tx_c.groupby(f"{t}.month").mean(t),
            "tmin_c": tn_c.groupby(f"{t2}.month").mean(t2),
            "frost_days": count_mean(tn_c < 0, tn_c.notnull(), t2),
            "summer_days": count_mean(tx_c >= 25, tx_c.notnull(), t),
        }
    )
    return out.drop_vars([v for v in ("number", "expver") if v in out.coords])
