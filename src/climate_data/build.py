"""Build the per-country datasets A (normals 1991-2020) and B (shift vs 1961-1990).

python -m climate_data.build --country LU [--cache cache/] [--out data/] [--offline] [--daily]
"""
from __future__ import annotations

import argparse
import calendar
import logging
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from . import countries, datapackage, fetch_cds, grid, normals, shift, urls

log = logging.getLogger("climate_data.build")

LAND_MONTHLY = "reanalysis-era5-land-monthly-means"
ERA5_MONTHLY = "reanalysis-era5-single-levels-monthly-means"
LAND_DAILY = "derived-era5-land-daily-statistics"
ERA5_DAILY = "derived-era5-single-levels-daily-statistics"
SOURCES = {"era5-land": (LAND_MONTHLY, LAND_DAILY), "era5": (ERA5_MONTHLY, ERA5_DAILY)}

YEARS = list(range(1961, 2021))
OLD = (1961, 1990)
NEW = (1991, 2020)
PERIOD = "1991-2020"
CHUNK = 10

PLACE_COLS = ["country", "code", "name", "admin1_code", "admin1_name", "admin2_code", "admin2_name"]
CELL_KEYS = ["grid_source", "grid_lat", "grid_lon"]
MONTHLY_VARS = ["tmean_c", "precip_mm"]
DAILY_VARS = ["tmin_c", "tmax_c", "frost_days", "summer_days"]
STATS = {"tmax": "daily_maximum", "tmin": "daily_minimum"}


# --------------------------------------------------------------------------- requests
def monthly_request() -> dict:
    return {
        "product_type": "monthly_averaged_reanalysis",
        "variable": ["2m_temperature", "total_precipitation"],
        "month": [f"{m:02d}" for m in range(1, 13)],
        "time": ["00:00"],
    }


def daily_request(dataset: str, stat: str, month: int) -> dict:
    req = {
        "variable": ["2m_temperature"],
        "month": f"{month:02d}",
        "day": [f"{d:02d}" for d in range(1, calendar.monthrange(2000, month)[1] + 1)],
        "daily_statistic": STATS[stat],
        "time_zone": "utc+00:00",
        "frequency": "1_hourly",
    }
    if dataset == ERA5_DAILY:
        req = {"product_type": "reanalysis", **req}
    return req


def cached_files(dataset: str, request: dict, bbox, years, cache: Path, chunk: int) -> list[Path]:
    """The paths fetch_cds.fetch writes, without downloading."""
    return [Path(cache) / fetch_cds.file_name(dataset, request, bbox, ys[0], ys[-1])
            for ys in fetch_cds.year_chunks(years, chunk)]


def get_files(dataset, request, bbox, years, cache, chunk, offline) -> list[Path] | None:
    """Files for the request; None when offline and any is missing from the cache."""
    if offline:
        files = cached_files(dataset, request, bbox, years, cache, chunk)
        missing = [f for f in files if not (f.exists() and f.stat().st_size > 0)]
        if missing:
            log.warning("offline: %d of %d %s files missing in %s (first %s)",
                        len(missing), len(files), dataset, cache, missing[0].name)
            return None
        return files
    return fetch_cds.fetch(dataset, request, bbox, years, cache, chunk=chunk)


# --------------------------------------------------------------------------- netcdf
def _name(ds, names) -> str:
    for n in names:
        if n in ds.dims or n in ds.coords:
            return n
    raise ValueError(f"dataset has none of {names}")


def _time(ds) -> str:
    return _name(ds, ("valid_time", "time"))


def open_grid(path: Path) -> xr.Dataset:
    with xr.open_dataset(path) as ds:
        return ds.load()


def at_cells(ds: xr.Dataset, lats: np.ndarray, lons: np.ndarray) -> xr.Dataset:
    """Values at the given grid cells, dim 'cell' (exact cells, checked)."""
    la, lo = _name(ds, ("latitude", "lat")), _name(ds, ("longitude", "lon"))
    lons = np.asarray(lons, dtype=float)
    if float(ds[lo].max()) > 180:
        lons = np.where(lons < 0, lons + 360.0, lons)
    out = ds.sel({la: xr.DataArray(np.asarray(lats, float), dims="cell"),
                  lo: xr.DataArray(lons, dims="cell")}, method="nearest")
    if (np.abs(out[la].values - lats) > 1e-3).any() or (np.abs(out[lo].values - lons) > 1e-3).any():
        raise ValueError("grid cells not found in NetCDF file (grid mismatch)")
    return out.drop_vars([la, lo])


def series_at_cells(files: list[Path], lats, lons, var: str | None = None) -> xr.Dataset | xr.DataArray:
    parts = []
    for f in files:
        with xr.open_dataset(f) as ds:
            sub = at_cells(ds, lats, lons)
            if var == "first":
                names = [v for v in sub.data_vars if v not in ("expver", "number")]
                sub = sub[names[0]]
            parts.append(sub.load())
    t = _time(parts[0])
    return xr.concat(parts, dim=t).sortby(t)


def _frame(ds: xr.Dataset, cells: pd.DataFrame, vars_: list[str]) -> pd.DataFrame:
    rows = []
    for m in range(1, 13):
        part = cells[CELL_KEYS].copy()
        part["month"] = m
        for v in vars_:
            part[v] = ds[v].sel(month=m).transpose("cell").values
        rows.append(part)
    return pd.concat(rows, ignore_index=True)


# --------------------------------------------------------------------------- per box
def box_normals(country, box, places: pd.DataFrame, cache: Path, offline: bool, daily: bool):
    """Assign cells for the places in one box and compute both periods' normals per cell.

    Returns (places with cells, old normals, new normals, daily_ok).
    """
    req = monthly_request()
    land = get_files(LAND_MONTHLY, req, box.bbox, YEARS, cache, CHUNK, offline)
    if land is None:
        raise FileNotFoundError(f"{country.code} {box.name}: ERA5-Land monthly files missing from {cache}")
    era5 = get_files(ERA5_MONTHLY, req, box.bbox, YEARS, cache, CHUNK, offline)
    if era5 is None:
        log.warning("%s: no ERA5 fallback in cache, ERA5-Land only", box.name)
    files = {"era5-land": land, "era5": era5}

    primary = open_grid(land[0])["t2m"]
    fallback = open_grid(era5[0])["t2m"] if era5 else None
    placed = grid.assign_cells(places, primary, fallback)
    cells_all = grid.unique_cells(placed)

    old_parts, new_parts = [], []
    daily_ok = daily
    for src, cells in cells_all.groupby("grid_source", sort=True):
        cells = cells.reset_index(drop=True)
        lats, lons = cells["grid_lat"].to_numpy(), cells["grid_lon"].to_numpy()
        ds = series_at_cells(files[src], lats, lons)
        o = _frame(normals.monthly_normals(ds, *OLD), cells, MONTHLY_VARS)
        n = _frame(normals.monthly_normals(ds, *NEW), cells, MONTHLY_VARS)
        if daily_ok:
            d = daily_series(src, box, cache, offline, lats, lons)
            if d is None:
                daily_ok = False
            else:
                tx, tn = d
                o = o.merge(_frame(normals.daily_normals(tx, tn, *OLD), cells, DAILY_VARS),
                            on=CELL_KEYS + ["month"])
                n = n.merge(_frame(normals.daily_normals(tx, tn, *NEW), cells, DAILY_VARS),
                            on=CELL_KEYS + ["month"])
        old_parts.append(o)
        new_parts.append(n)
    old = pd.concat(old_parts, ignore_index=True)
    new = pd.concat(new_parts, ignore_index=True)
    if not daily_ok:
        old = old.drop(columns=[c for c in DAILY_VARS if c in old.columns])
        new = new.drop(columns=[c for c in DAILY_VARS if c in new.columns])
    return placed, old, new, daily_ok


def daily_series(src, box, cache, offline, lats, lons):
    dataset = SOURCES[src][1]
    out = {}
    for stat in STATS:
        files = []
        for m in range(1, 13):
            got = get_files(dataset, daily_request(dataset, stat, m), box.bbox, YEARS, cache, 1, offline)
            if got is None:
                log.warning("--daily: %s %s data missing, daily columns dropped", dataset, stat)
                return None
            files += got
        out[stat] = series_at_cells(files, lats, lons, var="first")
    return out["tmax"], out["tmin"]


# --------------------------------------------------------------------------- build
def split_by_box(country, places: pd.DataFrame) -> list[tuple[object, pd.DataFrame]]:
    lat, lon = places["latitude"].to_numpy(), places["longitude"].to_numpy()
    taken = np.zeros(len(places), bool)
    out = []
    for box in country.boxes:
        inside = box.contains(lat, lon) & ~taken
        taken |= inside
        if inside.any():
            out.append((box, places[inside].reset_index(drop=True)))
    if (~taken).any():
        bad = places.loc[~taken, ["code", "name"]].head(5).to_dict("records")
        if not country.drop_outside:
            raise ValueError(f"{int((~taken).sum())} {country.code} places outside every box, e.g. {bad}")
        log.info("%s: %d places outside the covered area dropped (%s)", country.code, int((~taken).sum()), bad)
    return out


def add_urls(places: pd.DataFrame, cc: str, urls_path: Path | None) -> pd.DataFrame:
    p = urls_path or urls.URLS_DIR / f"{cc}.csv"
    if not Path(p).exists():
        log.warning("no URL file %s, weatheo_url left empty", p)
        out = places.copy()
        out["weatheo_url"] = ""
        return out
    return urls.join_urls(places, urls.load_urls(cc, p), cc, verbose=False)


def build(cc: str, cache: Path, out: Path, offline: bool = False, daily: bool = False,
          places_path: Path | None = None, urls_path: Path | None = None) -> dict:
    country = countries.get(cc)
    places = country.load_places(places_path)
    n_loaded = len(places)
    placed, olds, news, daily_ok = [], [], [], daily
    for box, sub in split_by_box(country, places):
        p, o, n, ok = box_normals(country, box, sub, Path(cache), offline, daily)
        placed.append(p)
        olds.append(o)
        news.append(n)
        daily_ok = daily_ok and ok
    places = pd.concat(placed, ignore_index=True)
    old = pd.concat(olds, ignore_index=True).drop_duplicates(CELL_KEYS + ["month"])
    new = pd.concat(news, ignore_index=True).drop_duplicates(CELL_KEYS + ["month"])
    vars_ = MONTHLY_VARS + (DAILY_VARS if daily_ok else [])
    old, new = old[CELL_KEYS + ["month"] + vars_], new[CELL_KEYS + ["month"] + vars_]

    places = add_urls(places, country.code, urls_path)
    places = places.sort_values("code").reset_index(drop=True)
    base = places[PLACE_COLS + ["latitude", "longitude"] + CELL_KEYS + ["weatheo_url"]]

    a_new = base.merge(new, on=CELL_KEYS, how="left", validate="many_to_many")
    a_old = base.merge(old, on=CELL_KEYS, how="left", validate="many_to_many")
    for t in (a_new, a_old):
        if len(t) != 12 * len(base):
            raise ValueError(f"expected {12 * len(base)} place-month rows, got {len(t)}")
        if t[MONTHLY_VARS].isna().any().any():
            raise ValueError("NaN normals for some places: the grid has gaps at assigned cells")

    a = a_new.sort_values(["code", "month"]).reset_index(drop=True)
    a[vars_] = a[vars_].round(1)
    a["period"] = PERIOD
    a = a[PLACE_COLS + ["latitude", "longitude", "grid_lat", "grid_lon", "grid_source", "month"] + vars_ + ["period", "weatheo_url"]]
    b = shift.compute_shift(a_old, a_new)

    out_dir = Path(out) / country.code
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = country.code.lower()
    names = {
        "A": f"{stem}_climate_normals_1991_2020",
        "B": f"{stem}_climate_shift_1961_1990_vs_1991_2020",
    }
    for key, df in (("A", a), ("B", b)):
        df.to_csv(out_dir / f"{names[key]}.csv", index=False, encoding="utf-8")
        df.to_parquet(out_dir / f"{names[key]}.parquet", index=False)
    pkg = datapackage.build_package(
        country, {names["A"]: a, names["B"]: b}, daily=daily_ok,
        n_places=len(places), n_loaded=n_loaded,
    )
    datapackage.write(out_dir, pkg)
    return {"A": a, "B": b, "package": pkg, "dir": out_dir, "daily": daily_ok}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m climate_data.build", description=__doc__.splitlines()[0])
    ap.add_argument("--country", required=True, choices=sorted(countries.COUNTRIES))
    ap.add_argument("--cache", type=Path, default=Path("cache"))
    ap.add_argument("--out", type=Path, default=Path("data"))
    ap.add_argument("--offline", action="store_true", help="read only the cache, never call CDS")
    ap.add_argument("--daily", action="store_true", help="add tmin/tmax/frost/summer day columns")
    ap.add_argument("--places", type=Path, default=None, help="places source file/dir (default places/raw/<cc>)")
    ap.add_argument("--urls", type=Path, default=None, help="URL list (default places/urls/<CC>.csv)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    t0 = time.perf_counter()
    res = build(args.country, args.cache, args.out, args.offline, args.daily, args.places, args.urls)
    print(f"{args.country}: A {len(res['A'])} rows, B {len(res['B'])} rows, daily={res['daily']}, "
          f"-> {res['dir']} in {time.perf_counter() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
