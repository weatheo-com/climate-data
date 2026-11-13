"""Hourly ERA5-Land timeseries to local civil days.

Pure functions: read the CDS ``reanalysis-era5-land-timeseries`` CSV ZIP and
aggregate hourly values to complete local days in an IANA timezone.

Conventions:
- t2m, u10, v10 are instantaneous at ``valid_time``: they belong to the local
  day of ``valid_time``.
- tp, ssrd are amounts for the hour ending at ``valid_time``: they belong to the
  local day of ``valid_time - 1 h``.
- A day is kept only when every hour of that local day (23, 24 or 25 on DST
  days) is present for each convention that has data.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

VARS = ("t2m", "tp", "u10", "v10", "ssrd")
INSTANT = ("t2m", "u10", "v10")
AMOUNT = ("tp", "ssrd")
HOUR = pd.Timedelta(hours=1)

COLUMNS = [
    "date",
    "tmean_c",
    "tmin_c",
    "tmax_c",
    "precip_mm",
    "wind_mean_kmh",
    "wind_max_kmh",
    "solar_kwh_m2",
]


def read_timeseries_zip(path: str | Path) -> tuple[pd.DataFrame, float | None, float | None]:
    """Read a CDS timeseries ZIP of CSVs.

    Returns ``(hourly, latitude, longitude)``: ``hourly`` is indexed by
    ``valid_time`` (tz-aware UTC, sorted, unique) with whichever of
    t2m (K), tp (m), u10, v10 (m/s), ssrd (J/m2) the ZIP holds.
    """
    frames: list[pd.DataFrame] = []
    lat = lon = None
    with zipfile.ZipFile(path) as zf:
        for name in sorted(zf.namelist()):
            if not name.lower().endswith(".csv"):
                continue
            df = pd.read_csv(io.BytesIO(zf.read(name)))
            if "valid_time" not in df.columns:
                continue
            if lat is None and "latitude" in df.columns and len(df):
                lat = float(df["latitude"].iloc[0])
            if lon is None and "longitude" in df.columns and len(df):
                lon = float(df["longitude"].iloc[0])
            keep = [c for c in df.columns if c in VARS]
            if not keep:
                continue
            t = pd.to_datetime(df["valid_time"])
            t = t.dt.tz_localize("UTC") if t.dt.tz is None else t.dt.tz_convert("UTC")
            sub = df[keep].astype(float)
            sub.index = pd.DatetimeIndex(t, name="valid_time")
            sub = sub[~sub.index.duplicated(keep="first")]
            frames.append(sub)
    if not frames:
        hourly = pd.DataFrame(index=pd.DatetimeIndex([], tz="UTC", name="valid_time"))
    else:
        hourly = frames[0]
        for f in frames[1:]:
            f = f[[c for c in f.columns if c not in hourly.columns]]
            if f.shape[1]:
                hourly = hourly.join(f, how="outer")
        hourly = hourly.sort_index()
    return hourly, lat, lon


def _utc_index(idx: pd.Index) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(idx)
    return idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")


def _local_dates(idx: pd.DatetimeIndex, timezone: str) -> np.ndarray:
    return np.asarray(idx.tz_convert(timezone).date)


def to_daily(hourly: pd.DataFrame, timezone: str, temp_offset_c: float = 0.0) -> pd.DataFrame:
    """Aggregate hourly values to complete local civil days in ``timezone``."""
    present = [v for v in VARS if v in hourly.columns]
    has_t = "t2m" in present
    has_w = "u10" in present and "v10" in present
    has_p = "tp" in present
    has_s = "ssrd" in present
    cols = ["date"]
    if has_t:
        cols += ["tmean_c", "tmin_c", "tmax_c"]
    if has_p:
        cols.append("precip_mm")
    if has_w:
        cols += ["wind_mean_kmh", "wind_max_kmh"]
    if has_s:
        cols.append("solar_kwh_m2")
    if hourly.empty or not (has_t or has_w or has_p or has_s):
        return pd.DataFrame(columns=cols)

    h = hourly[present].copy()
    h.index = _utc_index(h.index)
    h = h[~h.index.duplicated(keep="first")].sort_index()
    h = h[h.index == h.index.floor("h")]

    # Expected hours per local day, counted over a full UTC hour range.
    full = pd.date_range(h.index.min().floor("D") - pd.Timedelta(days=2),
                         h.index.max().ceil("D") + pd.Timedelta(days=2), freq="h", tz="UTC")
    expected = pd.Series(1, index=_local_dates(full, timezone)).groupby(level=0).sum()

    inst_day = _local_dates(h.index, timezone)
    amt_day = _local_dates(h.index - HOUR, timezone)

    parts: dict[str, pd.Series] = {}
    complete: pd.Series | None = None

    def _check(mask: pd.Series, day: np.ndarray) -> None:
        nonlocal complete
        n = pd.Series(mask.to_numpy().astype(int), index=day).groupby(level=0).sum()
        ok = n == expected.reindex(n.index)
        if complete is None:
            complete = ok
        else:
            both = complete.index.union(ok.index)
            complete = complete.reindex(both, fill_value=False) & ok.reindex(both, fill_value=False)

    if has_t:
        t = pd.Series(h["t2m"].to_numpy() - 273.15 + temp_offset_c, index=inst_day)
        _check(h["t2m"].notna(), inst_day)
        g = t.groupby(level=0)
        parts["tmean_c"] = g.mean()
        parts["tmin_c"] = g.min()
        parts["tmax_c"] = g.max()
    if has_w:
        ws = np.sqrt(h["u10"].to_numpy() ** 2 + h["v10"].to_numpy() ** 2) * 3.6
        _check(h["u10"].notna() & h["v10"].notna(), inst_day)
        g = pd.Series(ws, index=inst_day).groupby(level=0)
        parts["wind_mean_kmh"] = g.mean()
        parts["wind_max_kmh"] = g.max()
    if has_p:
        tp = h["tp"].clip(lower=0)
        _check(h["tp"].notna(), amt_day)
        parts["precip_mm"] = pd.Series(tp.to_numpy(), index=amt_day).groupby(level=0).sum() * 1000.0
    if has_s:
        _check(h["ssrd"].notna(), amt_day)
        parts["solar_kwh_m2"] = pd.Series(h["ssrd"].to_numpy(), index=amt_day).groupby(level=0).sum() / 3.6e6

    assert complete is not None
    days = sorted(d for d, ok in complete.items() if ok)
    out = pd.DataFrame({"date": days})
    for c in cols[1:]:
        s = parts[c].reindex(days).to_numpy(dtype=float)
        out[c] = np.round(s, 2 if c == "solar_kwh_m2" else 1)
    return out[cols].reset_index(drop=True)
