"""Elevations for the altitude adjustment of temperatures.

A reanalysis grid cell has one model elevation (its orography); a town can sit far
below or above it (Chamonix: town 1,035 m, its 0.1 deg ERA5-Land cell ~2,000 m). Each
place's temperatures are moved to its own elevation with a fixed lapse rate:

    t_place = t_cell + LAPSE_RATE * (grid_elevation_m - elevation_m)

- elevation_m: Copernicus DEM GLO-90 at the place's reference point.
- grid_elevation_m: model orography of the cell (ERA5-Land: ECMWF's published 0.1 deg
  geopotential file; ERA5: the CDS 'geopotential' field), geopotential / g.

Precipitation is not adjusted.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
import xarray as xr

log = logging.getLogger("climate_data.elevation")

LAPSE_RATE = 0.0065  # degC per m (ICAO standard atmosphere)
G = 9.80665  # m s-2, used by ECMWF to turn geopotential into height
TEMP_VARS = ("tmean_c", "tmin_c", "tmax_c")

LAND_GEO_URL = ("https://confluence.ecmwf.int/download/attachments/140385202/"
                "geo_1279l4_0.1x0.1.grib2_v4_unpack.nc")
LAND_GEO_FILE = Path("orography") / "era5-land-geo.nc"
DEM_URL = "https://copernicus-dem-90m.s3.amazonaws.com/{name}/{name}.tif"
DEM_DIR = Path("dem")
ERA5_OROGRAPHY_REQUEST = {
    "product_type": "monthly_averaged_reanalysis",
    "variable": ["geopotential"],
    "month": ["01"],
    "time": ["00:00"],
}
ERA5_OROGRAPHY_YEARS = [2020]


def dem_tile_name(lat_floor: int, lon_floor: int) -> str:
    ns = "N" if lat_floor >= 0 else "S"
    ew = "E" if lon_floor >= 0 else "W"
    return f"Copernicus_DSM_COG_30_{ns}{abs(lat_floor):02d}_00_{ew}{abs(lon_floor):03d}_00_DEM"


def _download(url: str, path: Path, offline: bool) -> Path | None:
    """Cached download. None when the server has no such file (404: DEM tile over sea)."""
    if path.exists() and path.stat().st_size > 0:
        return path
    missing = path.with_name(path.name + ".missing")
    if missing.exists():
        return None
    if offline:
        raise FileNotFoundError(f"offline: {path} not in cache")
    import requests

    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as r:
        if r.status_code in (403, 404):
            missing.touch()
            return None
        r.raise_for_status()
        part = path.with_name(path.name + ".part")
        with open(part, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    os.replace(part, path)
    return path


def place_elevation(lats, lons, cache: Path, offline: bool = False) -> np.ndarray:
    """Copernicus DEM GLO-90 height (m) at each point; NaN where no tile or no data."""
    import rasterio

    lats = np.asarray(lats, dtype=float)
    lons = np.asarray(lons, dtype=float)
    out = np.full(len(lats), np.nan)
    tiles = np.stack([np.floor(lats), np.floor(lons)], axis=1).astype(int)
    for la, lo in sorted({(int(a), int(b)) for a, b in tiles}):
        name = dem_tile_name(la, lo)
        path = _download(DEM_URL.format(name=name), Path(cache) / DEM_DIR / f"{name}.tif", offline)
        if path is None:
            continue
        idx = np.flatnonzero((tiles[:, 0] == la) & (tiles[:, 1] == lo))
        with rasterio.open(path) as r:
            vals = np.array([v[0] for v in r.sample(zip(lons[idx], lats[idx]))], dtype=float)
            if r.nodata is not None:
                vals[vals == r.nodata] = np.nan
        out[idx] = vals
    return out


def _orography_at(z: xr.DataArray, lats, lons, tol: float) -> np.ndarray:
    la = "latitude" if "latitude" in z.dims else "lat"
    lo = "longitude" if "longitude" in z.dims else "lon"
    for d in list(z.dims):
        if d not in (la, lo):
            z = z.isel({d: 0})
    lats = np.asarray(lats, dtype=float)
    lons = np.asarray(lons, dtype=float)
    if float(z[lo].max()) > 180:
        lons = np.where(lons < 0, lons + 360.0, lons)
    sel = z.sel({la: xr.DataArray(lats, dims="cell"), lo: xr.DataArray(lons, dims="cell")}, method="nearest")
    if (np.abs(sel[la].values - lats) > tol).any() or (np.abs(sel[lo].values - lons) > tol).any():
        raise ValueError("orography grid does not match the data grid")
    return sel.values.astype(float) / G


def land_orography(lats, lons, cache: Path, offline: bool = False) -> np.ndarray:
    path = _download(LAND_GEO_URL, Path(cache) / LAND_GEO_FILE, offline)
    if path is None:
        raise FileNotFoundError(f"ERA5-Land orography not available at {LAND_GEO_URL}")
    with xr.open_dataset(path) as ds:
        return _orography_at(ds["z"].load(), lats, lons, tol=0.01)


def era5_orography(lats, lons, path: Path) -> np.ndarray:
    with xr.open_dataset(path) as ds:
        return _orography_at(ds["z"].load(), lats, lons, tol=0.01)


def cell_elevation(placed, cache: Path, era5_file: Path | None, offline: bool = False) -> np.ndarray:
    """Model elevation (m, rounded) of each place's assigned cell."""
    src = placed["grid_source"].to_numpy()
    lat = placed["grid_lat"].to_numpy(dtype=float)
    lon = placed["grid_lon"].to_numpy(dtype=float)
    out = np.full(len(placed), np.nan)
    land = src == "era5-land"
    if land.any():
        out[land] = land_orography(lat[land], lon[land], cache, offline)
    if (~land).any():
        if era5_file is None:
            raise FileNotFoundError("ERA5 orography file needed for era5 fallback cells")
        out[~land] = era5_orography(lat[~land], lon[~land], era5_file)
    return np.round(out)


def adjust(df, cols=TEMP_VARS):
    """Move temperature columns from the cell elevation to the place elevation (copy)."""
    df = df.copy()
    delta = LAPSE_RATE * (df["grid_elevation_m"].astype(float) - df["elevation_m"].astype(float))
    for c in cols:
        if c in df.columns:
            df[c] = df[c].astype(float) + delta
    return df


def fill_missing(place_m: np.ndarray, cell_m: np.ndarray) -> tuple[np.ndarray, int]:
    """Places with no DEM value take the cell elevation (no adjustment). Returns (values, count)."""
    miss = ~np.isfinite(place_m)
    out = np.where(miss, cell_m, np.round(place_m))
    return out, int(miss.sum())


__all__ = ["LAPSE_RATE", "TEMP_VARS", "dem_tile_name", "place_elevation", "cell_elevation",
           "adjust", "fill_missing", "ERA5_OROGRAPHY_REQUEST", "ERA5_OROGRAPHY_YEARS"]
