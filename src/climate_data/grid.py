"""Map places (municipalities) to the nearest valid cell of a regular lat/lon grid.

ERA5-Land (0.1 deg) is the primary grid; its sea cells are NaN. A place whose
nearest land cell is more than ``PRIMARY_WINDOW`` cells away falls back to the
ERA5 single-levels grid (0.25 deg), which has values everywhere.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import xarray as xr

PRIMARY_WINDOW = 3  # cells searched around a place in the primary grid
EARTH_RADIUS_KM = 6371.0

_LAT_NAMES = ("latitude", "lat")
_LON_NAMES = ("longitude", "lon")


def _coord_name(da: xr.DataArray, names: tuple[str, ...]) -> str:
    for n in names:
        if n in da.dims:
            return n
    raise ValueError(f"grid has none of the dims {names}: {da.dims}")


def _grid_parts(da: xr.DataArray):
    """Return lat (n), lon (m) coordinate arrays and a (n, m) bool mask of valid cells."""
    lat_n = _coord_name(da, _LAT_NAMES)
    lon_n = _coord_name(da, _LON_NAMES)
    other = [d for d in da.dims if d not in (lat_n, lon_n)]
    valid = da.notnull()
    if other:
        valid = valid.any(dim=other)
    valid = valid.transpose(lat_n, lon_n).values.astype(bool)
    lats = np.asarray(da[lat_n].values, dtype=np.float64)
    lons = np.asarray(da[lon_n].values, dtype=np.float64)
    return lats, lons, valid


def _fractional_index(coords: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Fractional index of values on a regular (ascending or descending) axis."""
    if len(coords) == 1:
        return np.zeros_like(values)
    step = (coords[-1] - coords[0]) / (len(coords) - 1)
    return (values - coords[0]) / step


def _search(lat_p, lon_p, lats, lons, valid, k):
    """Nearest valid cell within a (2k+1)^2 window around each point.

    Returns (row, col) int arrays, -1 where nothing valid was found.
    """
    n, m = valid.shape
    fi = _fractional_index(lats, lat_p)
    fj = _fractional_index(lons, lon_p)
    i0 = np.rint(fi).astype(np.int64)
    j0 = np.rint(fj).astype(np.int64)
    off = np.arange(-k, k + 1)
    di, dj = np.meshgrid(off, off, indexing="ij")
    ii = i0[:, None] + di.ravel()[None, :]  # (N, W)
    jj = j0[:, None] + dj.ravel()[None, :]
    inside = (ii >= 0) & (ii < n) & (jj >= 0) & (jj < m)
    iic = np.clip(ii, 0, n - 1)
    jjc = np.clip(jj, 0, m - 1)
    ok = inside & valid[iic, jjc]
    # Equirectangular distance (fine at these scales), in radians squared.
    clat = np.radians(lats[iic])
    clon = np.radians(lons[jjc])
    plat = np.radians(lat_p)[:, None]
    plon = np.radians(lon_p)[:, None]
    x = (clon - plon) * np.cos((clat + plat) / 2)
    y = clat - plat
    d2 = np.where(ok, x * x + y * y, np.inf)
    best = np.argmin(d2, axis=1)
    rows = np.arange(len(lat_p))
    found = np.isfinite(d2[rows, best])
    bi = np.where(found, iic[rows, best], -1)
    bj = np.where(found, jjc[rows, best], -1)
    return bi, bj


def _nearest(lat_p, lon_p, da, k_start, widen):
    lats, lons, valid = _grid_parts(da)
    if lons.max() > 180:
        lon_p = np.mod(lon_p, 360.0)
    bi = np.full(len(lat_p), -1, dtype=np.int64)
    bj = np.full(len(lat_p), -1, dtype=np.int64)
    todo = np.arange(len(lat_p))
    k = k_start
    k_max = max(valid.shape)
    while len(todo):
        ti, tj = _search(lat_p[todo], lon_p[todo], lats, lons, valid, k)
        hit = ti >= 0
        bi[todo[hit]] = ti[hit]
        bj[todo[hit]] = tj[hit]
        todo = todo[~hit]
        if not widen or k >= k_max:
            break
        k = min(k * 2, k_max)
    found = bi >= 0
    glat = np.where(found, lats[np.clip(bi, 0, None)], np.nan)
    glon = np.where(found, lons[np.clip(bj, 0, None)], np.nan)
    if lons.max() > 180:
        glon = np.where(glon > 180, glon - 360.0, glon)
    return glat, glon, found


def assign_cells(
    places: pd.DataFrame,
    primary: xr.DataArray,
    fallback: xr.DataArray | None,
) -> pd.DataFrame:
    """Add grid_lat, grid_lon, grid_source to places.

    Nearest non-NaN primary cell within PRIMARY_WINDOW cells ('era5-land'),
    otherwise nearest non-NaN fallback cell ('era5'). Without a fallback the
    primary search widens until a valid cell is found.
    """
    out = places.copy()
    lat_p = out["latitude"].to_numpy(dtype=np.float64)
    lon_p = out["longitude"].to_numpy(dtype=np.float64)
    glat, glon, found = _nearest(lat_p, lon_p, primary, PRIMARY_WINDOW, widen=fallback is None)
    source = np.where(found, "era5-land", "").astype(object)
    if fallback is not None and (~found).any():
        miss = np.flatnonzero(~found)
        flat, flon, ffound = _nearest(lat_p[miss], lon_p[miss], fallback, PRIMARY_WINDOW, widen=True)
        glat[miss] = flat
        glon[miss] = flon
        source[miss] = np.where(ffound, "era5", "")
    if (source == "").any():
        bad = out.loc[source == "", ["latitude", "longitude"]].head(5).to_dict("records")
        raise ValueError(f"{int((source == '').sum())} places have no valid grid cell, e.g. {bad}")
    out["grid_lat"] = np.round(glat, 2)
    out["grid_lon"] = np.round(glon, 2)
    out["grid_source"] = source.astype(str)
    return out


def unique_cells(places: pd.DataFrame) -> pd.DataFrame:
    """Distinct (grid_source, grid_lat, grid_lon) rows, sorted."""
    cols = ["grid_source", "grid_lat", "grid_lon"]
    return places[cols].drop_duplicates().sort_values(cols).reset_index(drop=True)
