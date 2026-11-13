"""Build the city datasets (daily weather, monthly climate, normals, annual indicators) of one country.

python -m climate_data.build_cities --country GB [--ranks 1-100] [--cache cache/timeseries] [--out data/cities]

Reads places/cities/<cc>.csv (climate_data.cities) and the ERA5-Land time-series ZIPs fetched by
climate_data.fetch_timeseries (<cache>/<CC>/<city_id>.zip + manifest.csv). No network except the
elevation lookups (Copernicus DEM tiles, ERA5-Land orography), which are cached under --elev-cache.
"""
from __future__ import annotations

import argparse
import io
import re
import sys
import unicodedata
import zipfile
from datetime import date
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from . import daily as daily_mod
from . import datapackage, elevation, indicators, urls
from .cities import OUTPUT_COLUMNS
from .fetch_timeseries import parse_ranks

FIRST_DAY = date(1950, 1, 1)
LAST_DAY = date(2025, 12, 31)
ANNUAL_YEARS = (1951, 2025)
MIN_DAYS = 27_000
OK_STATUSES = ("ok", "neighbour")
TEMP_RANGE = (-45.0, 50.0)
PRECIP_DAY_RANGE = (0.0, 400.0)
PRECIP_YEAR_RANGE = (150.0, 3500.0)
SUMMARY_KEYS = [
    "tmean_annual_c", "precip_annual_mm", "trend_c_per_decade_1951_2025", "trend_c_per_decade_1981_2025",
    "warmest_year", "coldest_year", "wettest_year", "driest_year",
]
CITY_COLUMNS = OUTPUT_COLUMNS + ["grid_lat", "grid_lon", "elevation_m", "grid_elevation_m", "weatheo_url"] + SUMMARY_KEYS
ID_COLUMNS = ["country", "city_id", "name"]
COUNTRY_NAMES = {"GB": "United Kingdom", "DE": "Germany", "FR": "France", "PT": "Portugal",
                 "LU": "Luxembourg", "RS": "Serbia"}

ElevationFn = Callable[[np.ndarray, np.ndarray, np.ndarray, np.ndarray], tuple[np.ndarray, np.ndarray]]


class ValidationError(Exception):
    pass


def file_names(cc: str) -> dict[str, str]:
    c = cc.lower()
    return {
        "cities": f"{c}_cities.csv",
        "daily_parquet": f"{c}_city_daily_weather_1950_2025.parquet",
        "daily_zip": f"{c}_city_daily_weather_1950_2025_csv.zip",
        "monthly_csv": f"{c}_city_monthly_climate_1950_2025.csv",
        "monthly_parquet": f"{c}_city_monthly_climate_1950_2025.parquet",
        "normals": f"{c}_city_climate_normals_1991_2020.csv",
        "annual": f"{c}_city_annual_climate_indicators_1951_2025.csv",
        "datapackage": f"{c}_cities_datapackage.json",
    }


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "city"


def city_csv_name(cc: str, ascii_name: str, city_id) -> str:
    return f"{cc.lower()}_{slug(ascii_name)}_{city_id}_daily.csv"


def lookup_elevation(cache: Path, offline: bool = False) -> ElevationFn:
    """Real lookup: Copernicus DEM at the city point, ERA5-Land orography of the grid cell (as build.py)."""
    def fn(lats, lons, grid_lats, grid_lons):
        placed = pd.DataFrame({"grid_lat": grid_lats, "grid_lon": grid_lons, "grid_source": "era5-land"})
        cell = elevation.cell_elevation(placed, cache, None, offline)
        dem = elevation.place_elevation(lats, lons, cache, offline)
        place, _ = elevation.fill_missing(dem, cell)
        return place, cell
    return fn


def read_manifest(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["city_id", "grid_lat", "grid_lon", "status"])
    m = pd.read_csv(path, dtype={"city_id": str})
    return m.drop_duplicates("city_id", keep="last").set_index("city_id", drop=False)


def add_urls(cities: pd.DataFrame, cc: str, urls_path: Path | None) -> pd.Series:
    p = Path(urls_path) if urls_path else urls.URLS_DIR / f"{cc}.csv"
    if not p.exists():
        return pd.Series("", index=cities.index)
    places = cities.copy()
    if "code" not in places:
        places["code"] = ""
    return urls.join_urls(places, urls.load_urls(cc, p), cc, verbose=False)["weatheo_url"]


def validate(daily_all: pd.DataFrame, annual_all: pd.DataFrame, min_days: int = MIN_DAYS) -> list[str]:
    """Return a list of problems (empty when the data passes)."""
    errs: list[str] = []
    core = ["tmean_c", "tmin_c", "tmax_c", "precip_mm"]
    for c in core:
        if c not in daily_all:
            errs.append(f"column {c} missing from the daily data")
    if errs:
        return errs

    def where(mask: pd.Series, what: str):
        if mask.any():
            r = daily_all.loc[mask].iloc[0]
            errs.append(f"{int(mask.sum())} daily rows {what}, e.g. city {r['city_id']} ({r['name']}) on {r['date']}")

    where(daily_all[core].isna().any(axis=1), "with missing tmean/tmin/tmax/precip")
    t = daily_all[["tmean_c", "tmin_c", "tmax_c"]]
    where((t["tmin_c"] > t["tmean_c"]) | (t["tmean_c"] > t["tmax_c"]), "where tmin <= tmean <= tmax fails")
    where(((t < TEMP_RANGE[0]) | (t > TEMP_RANGE[1])).any(axis=1),
          f"with a temperature outside {TEMP_RANGE[0]:g}..{TEMP_RANGE[1]:g} C")
    p = daily_all["precip_mm"]
    where((p < PRECIP_DAY_RANGE[0]) | (p > PRECIP_DAY_RANGE[1]),
          f"with precip_mm outside {PRECIP_DAY_RANGE[0]:g}..{PRECIP_DAY_RANGE[1]:g}")
    dup = daily_all.duplicated(["city_id", "date"], keep=False)
    where(dup, "with a date repeated within a city")
    n = daily_all.groupby("city_id").size()
    short = n[n < min_days]
    if len(short):
        errs.append(f"{len(short)} cities have fewer than {min_days} days, e.g. "
                    + ", ".join(f"{k}: {v}" for k, v in short.head(5).items()))
    if len(annual_all):
        ap = annual_all["precip_mm"]
        bad = annual_all[(ap < PRECIP_YEAR_RANGE[0]) | (ap > PRECIP_YEAR_RANGE[1])]
        if len(bad):
            r = bad.iloc[0]
            errs.append(f"{len(bad)} city-years with annual precipitation outside "
                        f"{PRECIP_YEAR_RANGE[0]:g}..{PRECIP_YEAR_RANGE[1]:g} mm, e.g. city {r['city_id']} "
                        f"({r['name']}) {int(r['year'])}: {r['precip_mm']} mm")
    return errs


def _ids(city: pd.Series) -> dict:
    return {"country": city["country"], "city_id": city["city_id"], "name": city["name"]}


def _with_ids(df: pd.DataFrame, city: pd.Series) -> pd.DataFrame:
    df = df.copy()
    for i, (k, v) in enumerate(_ids(city).items()):
        df.insert(i, k, v)
    return df


def build(cc: str, cities_path: Path, cache: Path, out: Path, ranks: tuple[int, int] | None = None,
          elevation_fn: ElevationFn | None = None, urls_path: Path | None = None,
          min_days: int = MIN_DAYS, log=print) -> dict:
    """Build every file for one country. Raises ValidationError when a check fails (nothing written)."""
    cc = cc.upper()
    cities = pd.read_csv(cities_path, dtype={"city_id": str, "admin1_code": str}, keep_default_na=False,
                         na_values=[""])
    cities["admin1_code"] = cities["admin1_code"].fillna("")
    cities["admin1_name"] = cities["admin1_name"].fillna("")
    if ranks:
        cities = cities[cities["rank"].between(*ranks)]
    cities = cities.sort_values("rank").reset_index(drop=True)
    man = read_manifest(Path(cache) / cc / "manifest.csv")

    skipped: list[tuple[str, str, str]] = []
    keep, zips = [], {}
    for i, c in cities.iterrows():
        cid = c["city_id"]
        if cid not in man.index:
            skipped.append((cid, c["name"], "not fetched (no manifest line)"))
            continue
        st = str(man.at[cid, "status"])
        z = Path(cache) / cc / f"{cid}.zip"
        if st not in OK_STATUSES:
            skipped.append((cid, c["name"], f"manifest status {st}"))
        elif not z.exists():
            skipped.append((cid, c["name"], "zip missing"))
        else:
            keep.append(i)
            zips[cid] = z
    cities = cities.loc[keep].reset_index(drop=True)

    hourly, glat, glon = {}, [], []
    for _, c in cities.iterrows():
        h, la, lo = daily_mod.read_timeseries_zip(zips[c["city_id"]])
        hourly[c["city_id"]] = h
        glat.append(la if la is not None else float(man.at[c["city_id"], "grid_lat"]))
        glon.append(lo if lo is not None else float(man.at[c["city_id"], "grid_lon"]))
    cities["grid_lat"] = np.round(np.asarray(glat, dtype=float), 4)
    cities["grid_lon"] = np.round(np.asarray(glon, dtype=float), 4)
    if len(cities):
        fn = elevation_fn or lookup_elevation(Path("cache"))
        elev, gelev = fn(cities["latitude"].to_numpy(float), cities["longitude"].to_numpy(float),
                         cities["grid_lat"].to_numpy(float), cities["grid_lon"].to_numpy(float))
        cities["elevation_m"] = np.round(np.asarray(elev, dtype=float))
        cities["grid_elevation_m"] = np.round(np.asarray(gelev, dtype=float))
    else:
        cities["elevation_m"] = cities["grid_elevation_m"] = pd.Series(dtype=float)
    cities["weatheo_url"] = add_urls(cities, cc, urls_path) if len(cities) else pd.Series(dtype=str)

    dailies, monthlies, norms, annuals, summaries = [], [], [], [], []
    for _, c in cities.iterrows():
        offset = elevation.LAPSE_RATE * (c["grid_elevation_m"] - c["elevation_m"])
        d = daily_mod.to_daily(hourly.pop(c["city_id"]), c["timezone"], float(offset) if np.isfinite(offset) else 0.0)
        d = d[(d["date"] >= FIRST_DAY) & (d["date"] <= LAST_DAY)].reset_index(drop=True)
        m = indicators.monthly(d)
        a = indicators.annual(d)
        a = a[a["year"].between(*ANNUAL_YEARS)].reset_index(drop=True)
        dailies.append(_with_ids(d, c))
        monthlies.append(_with_ids(m, c))
        norms.append(_with_ids(indicators.normals(m, d), c))
        annuals.append(_with_ids(a, c))
        summaries.append(indicators.summary(a))
    for k in SUMMARY_KEYS:
        cities[k] = [s.get(k) for s in summaries]

    def cat(frames, cols=ID_COLUMNS):
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=cols)

    daily_all, monthly_all = cat(dailies), cat(monthlies)
    normals_all, annual_all = cat(norms), cat(annuals)
    errs = validate(daily_all, annual_all, min_days) if len(cities) else ["no city could be built"]
    if errs:
        raise ValidationError(f"{cc}: validation failed:\n  " + "\n  ".join(errs))

    out_dir = Path(out) / cc
    out_dir.mkdir(parents=True, exist_ok=True)
    names = file_names(cc)
    cities_out = cities[CITY_COLUMNS].copy()
    for k in ("warmest_year", "coldest_year", "wettest_year", "driest_year"):
        cities_out[k] = cities_out[k].astype("Int64")
    cities_out.to_csv(out_dir / names["cities"], index=False)
    daily_typed = daily_all.copy()
    daily_typed["date"] = pd.to_datetime(daily_typed["date"]).dt.date
    daily_typed.to_parquet(out_dir / names["daily_parquet"], index=False)
    with zipfile.ZipFile(out_dir / names["daily_zip"], "w", zipfile.ZIP_DEFLATED) as zf:
        for d, (_, c) in zip(dailies, cities.iterrows()):
            buf = io.StringIO()
            d.drop(columns=ID_COLUMNS).to_csv(buf, index=False)
            zf.writestr(city_csv_name(cc, c["ascii_name"], c["city_id"]), buf.getvalue())
    monthly_all.to_csv(out_dir / names["monthly_csv"], index=False)
    monthly_all.to_parquet(out_dir / names["monthly_parquet"], index=False)
    normals_all.to_csv(out_dir / names["normals"], index=False)
    annual_all.to_csv(out_dir / names["annual"], index=False)
    city_csv_sample = dailies[0].drop(columns=ID_COLUMNS)
    pkg = datapackage.build_city_package(
        cc, COUNTRY_NAMES.get(cc, cc),
        {"cities": cities_out, "daily": daily_typed, "daily_csv": city_csv_sample,
         "monthly": monthly_all, "normals": normals_all, "annual": annual_all},
        names, n_cities=len(cities_out))
    datapackage.write_named(out_dir / names["datapackage"], pkg)

    sizes = {n: (out_dir / n).stat().st_size for n in names.values()}
    report = {"country": cc, "built": len(cities_out), "skipped": skipped, "daily_rows": len(daily_all),
              "monthly_rows": len(monthly_all), "annual_rows": len(annual_all), "out_dir": str(out_dir),
              "sizes": sizes}
    log(f"[cities] {cc}: built {len(cities_out)} cities, skipped {len(skipped)}; rows daily {len(daily_all)}, "
        f"monthly {len(monthly_all)}, normals {len(normals_all)}, annual {len(annual_all)}")
    for cid, nm, why in skipped:
        log(f"  skipped {cid} {nm}: {why}")
    for n, s in sizes.items():
        log(f"  {n}: {s / 1e6:.2f} MB")
    return report


def main(argv: list[str] | None = None, elevation_fn: ElevationFn | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--country", required=True)
    ap.add_argument("--ranks", default=None, help="e.g. 1-100")
    ap.add_argument("--cities", default=None, help="city list CSV (default places/cities/<cc>.csv)")
    ap.add_argument("--cache", default="cache/timeseries")
    ap.add_argument("--elev-cache", default="cache", help="cache of DEM tiles and ERA5-Land orography")
    ap.add_argument("--urls", default=None, help="weatheo URL file (default places/urls/<CC>.csv)")
    ap.add_argument("--out", default="data/cities")
    ap.add_argument("--offline", action="store_true", help="no elevation downloads")
    ap.add_argument("--min-days", type=int, default=MIN_DAYS)
    a = ap.parse_args(argv)
    cc = a.country.upper()
    cities_path = Path(a.cities) if a.cities else Path("places/cities") / f"{cc.lower()}.csv"
    if not cities_path.exists():
        print(f"error: city list {cities_path} not found (run python -m climate_data.cities)", file=sys.stderr)
        return 1
    fn = elevation_fn or lookup_elevation(Path(a.elev_cache), a.offline)
    try:
        build(cc, cities_path, Path(a.cache), Path(a.out), parse_ranks(a.ranks), fn,
              Path(a.urls) if a.urls else None, a.min_days)
    except ValidationError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
