import numpy as np
import pandas as pd

from climate_data import elevation


def test_dem_tile_name():
    assert elevation.dem_tile_name(45, 6) == "Copernicus_DSM_COG_30_N45_00_E006_00_DEM"
    assert elevation.dem_tile_name(38, -10) == "Copernicus_DSM_COG_30_N38_00_W010_00_DEM"
    assert elevation.dem_tile_name(-1, -1) == "Copernicus_DSM_COG_30_S01_00_W001_00_DEM"


def test_adjust_only_temperatures():
    df = pd.DataFrame({"tmean_c": [10.0], "precip_mm": [50.0], "elevation_m": [1035], "grid_elevation_m": [2000]})
    out = elevation.adjust(df)
    assert out.tmean_c.iloc[0] == 10.0 + 0.0065 * 965
    assert out.precip_mm.iloc[0] == 50.0
    assert df.tmean_c.iloc[0] == 10.0  # input untouched


def test_fill_missing():
    vals, n = elevation.fill_missing(np.array([12.4, np.nan]), np.array([100.0, 250.0]))
    assert n == 1 and list(vals) == [12.0, 250.0]
