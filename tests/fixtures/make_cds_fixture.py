"""Write small synthetic CDS NetCDF files into a cache dir, named exactly as fetch_cds names them.

python tests/fixtures/make_cds_fixture.py <cache_dir> [--country LU] [--daily]

Layout follows the current CDS NetCDF output: dims valid_time, latitude (descending),
longitude; float32 data vars t2m (K) and tp (m/day monthly mean rate); coords
number (scalar) and expver (per valid_time). Values are synthetic, with known answers:

ERA5-Land monthly: t2m = 10 + m degC (1961-1990), 11 + m degC (1991-2020);
                   tp = 0.002 m/day (1961-1990), 0.0022 m/day (1991-2020).
ERA5 monthly:      t2m = m degC, tp = 0.001 m/day (different, so a wrong source shows).
Daily (ERA5-Land): tmax 20 degC (old) / 21 (new), July 24 (old) / 30 (new);
                   tmin 5 degC (old) / 6 (new), January -2 (old) / +0.5 (new).
"""
from __future__ import annotations

import argparse
import calendar
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from climate_data import build, countries, fetch_cds

K = 273.15


def _grid(bbox, step):
    n, w, s, e = bbox
    lats = np.round(np.arange(round(n / step) * step, s - step / 2, -step), 4)
    lons = np.round(np.arange(round(w / step) * step, e + step / 2, step), 4)
    return lats, lons


def _write(path: Path, times, lats, lons, data: dict[str, np.ndarray]):
    ds = xr.Dataset(
        {k: (("valid_time", "latitude", "longitude"), v.astype("float32")) for k, v in data.items()},
        coords={"valid_time": times, "latitude": lats, "longitude": lons,
                "number": 0, "expver": ("valid_time", np.full(len(times), "0001"))},
    )
    for k in data:
        ds[k].attrs["units"] = "K" if k == "t2m" else "m"
    path.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(path)


def land_t2m_c(year: int, month: int) -> float:
    return 10.0 + month + (1.0 if year >= 1991 else 0.0)


def land_tp(year: int) -> float:
    return 0.0022 if year >= 1991 else 0.002


def tmax_c(year: int, month: int) -> float:
    new = year >= 1991
    if month == 7:
        return 30.0 if new else 24.0
    return 21.0 if new else 20.0


def tmin_c(year: int, month: int) -> float:
    new = year >= 1991
    if month == 1:
        return 0.5 if new else -2.0
    return 6.0 if new else 5.0


def make(cache: Path, cc: str = "LU", daily: bool = False) -> list[Path]:
    cache = Path(cache)
    country = countries.get(cc)
    req = build.monthly_request()
    written = []
    for box in country.boxes:
        for dataset, step, t2m, tp in (
            (build.LAND_MONTHLY, 0.1, land_t2m_c, lambda y: land_tp(y)),
            (build.ERA5_MONTHLY, 0.25, lambda y, m: float(m), lambda y: 0.001),
        ):
            lats, lons = _grid(box.bbox, step)
            shape = (12, len(lats), len(lons))
            for path, ys in zip(build.cached_files(dataset, req, box.bbox, build.YEARS, cache, build.CHUNK),
                                fetch_cds.year_chunks(build.YEARS, build.CHUNK)):
                times, T, P = [], [], []
                for y in ys:
                    for m in range(1, 13):
                        times.append(pd.Timestamp(y, m, 1))
                        T.append(np.full(shape[1:], t2m(y, m) + K))
                        P.append(np.full(shape[1:], tp(y)))
                _write(path, pd.DatetimeIndex(times), lats, lons, {"t2m": np.array(T), "tp": np.array(P)})
                written.append(path)
        if daily:
            lats, lons = _grid(box.bbox, 0.1)
            for stat, fn in (("tmax", tmax_c), ("tmin", tmin_c)):
                for m in range(1, 13):
                    req_d = build.daily_request(build.LAND_DAILY, stat, m)
                    files = build.cached_files(build.LAND_DAILY, req_d, box.bbox, build.YEARS, cache, 1)
                    for path, y in zip(files, build.YEARS):
                        nd = calendar.monthrange(y, m)[1]
                        times = pd.date_range(f"{y}-{m:02d}-01", periods=nd, freq="D")
                        v = np.full((nd, len(lats), len(lons)), fn(y, m) + K)
                        _write(path, times, lats, lons, {"t2m": v})
                        written.append(path)
    return written


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cache", type=Path)
    ap.add_argument("--country", default="LU")
    ap.add_argument("--daily", action="store_true")
    a = ap.parse_args(argv)
    files = make(a.cache, a.country, a.daily)
    print(f"wrote {len(files)} NetCDF files to {a.cache}")


if __name__ == "__main__":
    main()
