import time

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from climate_data.grid import assign_cells, unique_cells


def _land_grid(descending=False):
    """0.1 deg grid over 40-50N, 0-10E; cells east of 4.95E are sea (NaN)."""
    lats = np.round(np.arange(40.0, 50.0001, 0.1), 2)
    if descending:
        lats = lats[::-1]
    lons = np.round(np.arange(0.0, 10.0001, 0.1), 2)
    vals = np.ones((2, len(lats), len(lons)), dtype=np.float32)
    vals[:, :, lons > 4.95] = np.nan
    return xr.DataArray(
        vals,
        dims=("time", "latitude", "longitude"),
        coords={"time": [0, 1], "latitude": lats, "longitude": lons},
    )


def _coarse_grid():
    lats = np.arange(50.0, 39.999, -0.25)
    lons = np.arange(0.0, 10.0001, 0.25)
    return xr.DataArray(
        np.ones((len(lats), len(lons))),
        dims=("latitude", "longitude"),
        coords={"latitude": lats, "longitude": lons},
    )


def _places(points):
    return pd.DataFrame(
        {
            "code": [str(i) for i in range(len(points))],
            "latitude": [p[0] for p in points],
            "longitude": [p[1] for p in points],
        }
    )


POINTS = [
    (45.0, 2.0),  # inland exact
    (45.03, 2.04),  # inland between cells
    (45.0, 5.02),  # coast: nearest cell 5.0 is sea -> 4.9
    (45.1, 8.1),  # far at sea -> 0.25 deg fallback
]
EXPECTED = [
    (45.0, 2.0, "era5-land"),
    (45.0, 2.0, "era5-land"),
    (45.0, 4.9, "era5-land"),
    (45.0, 8.0, "era5"),
]


@pytest.mark.parametrize("descending", [False, True])
def test_assign_cells(descending):
    out = assign_cells(_places(POINTS), _land_grid(descending), _coarse_grid())
    got = list(zip(out.grid_lat, out.grid_lon, out.grid_source))
    assert got == EXPECTED
    assert list(out.code) == ["0", "1", "2", "3"]


def test_unique_cells():
    out = assign_cells(_places(POINTS), _land_grid(), _coarse_grid())
    cells = unique_cells(out)
    assert len(cells) == 3
    assert set(cells.grid_source) == {"era5-land", "era5"}


def test_no_fallback_widens():
    out = assign_cells(_places([(45.0, 8.0)]), _land_grid(), None)
    assert (out.grid_lat[0], out.grid_lon[0], out.grid_source[0]) == (45.0, 4.9, "era5-land")


def test_timing_35000():
    rng = np.random.default_rng(0)
    pts = np.column_stack([rng.uniform(40, 50, 35000), rng.uniform(0, 10, 35000)])
    places = _places([tuple(p) for p in pts])
    t0 = time.perf_counter()
    out = assign_cells(places, _land_grid(True), _coarse_grid())
    assert time.perf_counter() - t0 < 10
    assert out.grid_source.notna().all()
    land = out.longitude < 4.9
    assert (out.grid_source[land] == "era5-land").all()
    assert (np.abs(out.grid_lat[land] - out.latitude[land]) <= 0.0501).all()
