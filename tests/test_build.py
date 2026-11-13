import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from climate_data import build, countries, datapackage

FIX = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(FIX))
import make_cds_fixture as mk  # noqa: E402

LU_PLACES = FIX / "lu_places"
N_PLACES = 10


def _run(cache, out, **kw):
    return build.build("LU", cache, out, offline=True, places_path=LU_PLACES, **kw)


@pytest.fixture(scope="module")
def monthly_cache(tmp_path_factory):
    cache = tmp_path_factory.mktemp("cache")
    mk.make(cache, "LU")
    return cache


@pytest.fixture(scope="module")
def daily_cache(tmp_path_factory):
    cache = tmp_path_factory.mktemp("cache_daily")
    mk.make(cache, "LU", daily=True)
    return cache


def test_monthly_build_rows_and_known_values(monthly_cache, tmp_path):
    rc = build.main(["--country", "LU", "--offline", "--cache", str(monthly_cache),
                     "--out", str(tmp_path), "--places", str(LU_PLACES)])
    assert rc == 0
    d = tmp_path / "LU"
    a = pd.read_csv(d / "lu_climate_normals_1991_2020.csv", dtype={"code": str, "admin1_code": str})
    b = pd.read_csv(d / "lu_climate_shift_1961_1990_vs_1991_2020.csv",
                    dtype={"code": str, "admin1_code": str, "month": str})
    assert len(a) == N_PLACES * 12 and len(b) == N_PLACES * 13
    assert list(a.columns) == [
        "country", "code", "name", "admin1_code", "admin1_name", "admin2_code", "admin2_name",
        "latitude", "longitude", "grid_lat", "grid_lon", "grid_source", "elevation_m", "grid_elevation_m", "month",
        "tmean_c", "precip_mm", "period", "weatheo_url"]
    assert not any(c.startswith(("tmin", "tmax", "frost", "summer")) for c in list(a.columns) + list(b.columns))
    assert (a.grid_source == "era5-land").all() and (a.period == "1991-2020").all()
    assert a.code.str.len().eq(4).all()
    # every place on a 0.1 deg cell within half a cell
    assert ((a.grid_lat - a.latitude).abs() <= 0.0501).all()
    for m in range(1, 13):
        rows = a[a.month == m]
        assert (rows.tmean_c == 11.0 + m).all()
    jan = a[a.month == 1]
    assert (jan.precip_mm == 68.2).all()  # 0.0022 m/day * 31 * 1000
    feb = a[a.month == 2]
    assert (feb.precip_mm == round(0.0022 * 1000 * (28 + 8 / 30), 1)).all()  # 8 leap years in 1991-2020

    bj = b[b.month == "1"]
    assert (bj.tmean_1961_1990_c == 11.0).all() and (bj.tmean_1991_2020_c == 12.0).all()
    assert (bj.tmean_shift_c == 1.0).all()
    assert (bj.precip_1961_1990_mm == 62.0).all() and (bj.precip_shift_pct == 10.0).all()
    ann = b[b.month == "annual"]
    assert (ann.tmean_1961_1990_c == 16.5).all() and (ann.tmean_1991_2020_c == 17.5).all()
    old_days = 365 + 7 / 30  # 7 leap years in 1961-1990
    assert np.allclose(ann.precip_1961_1990_mm, round(2.0 * old_days, 1), atol=0.11)

    pa = pd.read_parquet(d / "lu_climate_normals_1991_2020.parquet")
    pb = pd.read_parquet(d / "lu_climate_shift_1961_1990_vs_1991_2020.parquet")
    assert len(pa) == len(a) and len(pb) == len(b) and pa.code.iloc[0] == a.code.iloc[0]

    pkg = json.loads((d / "datapackage.json").read_text())
    assert pkg["licenses"][0]["name"] == "CC-BY-4.0"
    assert pkg["homepage"] == "https://weatheo.com/en/open-data"
    assert pkg["contributors"][0]["role"] == "publisher"
    assert "Copernicus Climate Change Service" in pkg["description"]
    assert any("era5-land-monthly" in s["path"] for s in pkg["sources"])
    res = {r["path"]: r for r in pkg["resources"]}
    for path, df in (("lu_climate_normals_1991_2020.csv", a),
                     ("lu_climate_shift_1961_1990_vs_1991_2020.csv", b)):
        assert [f["name"] for f in res[path]["schema"]["fields"]] == list(df.columns)
        assert (d / path).exists() and (d / path.replace(".csv", ".parquet")).exists()


def test_daily_missing_drops_columns(monthly_cache, tmp_path):
    res = _run(monthly_cache, tmp_path, daily=True)
    assert res["daily"] is False
    assert "tmin_c" not in res["A"].columns and "frost_days_shift" not in res["B"].columns


def test_daily_build_known_values(daily_cache, tmp_path):
    res = _run(daily_cache, tmp_path, daily=True)
    a, b = res["A"], res["B"]
    assert res["daily"] is True and len(a) == N_PLACES * 12 and len(b) == N_PLACES * 13
    for c in ("tmin_c", "tmax_c", "frost_days", "summer_days"):
        assert c in a.columns and a[c].notna().all()
    jul, jan = a[a.month == 7], a[a.month == 1]
    assert (jul.tmax_c == 30.0).all() and (jul.summer_days == 31.0).all()
    assert (jan.tmin_c == 0.5).all() and (jan.frost_days == 0.0).all()
    bj, bjul = b[b.month == "1"], b[b.month == "7"]
    assert (bj.frost_days_1961_1990 == 31.0).all() and (bj.frost_days_shift == -31.0).all()
    assert (bjul.summer_days_1961_1990 == 0.0).all() and (bjul.summer_days_shift == 31.0).all()
    assert (bjul.tmax_shift_c == 6.0).all()
    pkg = res["package"]
    assert any("daily-statistics" in s["path"] for s in pkg["sources"])


def test_fallback_to_era5(tmp_path):
    cache = tmp_path / "cache"
    mk.make(cache, "LU")
    req = build.monthly_request()
    box = countries.get("LU").boxes[0]
    for f in build.cached_files(build.LAND_MONTHLY, req, box.bbox, build.YEARS, cache, build.CHUNK):
        with xr.open_dataset(f) as ds:
            ds = ds.load()
        ds["t2m"][:] = np.nan
        ds["tp"][:] = np.nan
        ds.to_netcdf(f)
    res = _run(cache, tmp_path / "out")
    a = res["A"]
    assert (a.grid_source == "era5").all()
    assert (a[a.month == 1].tmean_c == 1.0).all() and (a[a.month == 1].precip_mm == 31.0).all()
    assert ((a.grid_lat * 4).round(6) % 1 == 0).all()  # 0.25 deg cells


def test_offline_missing_cache_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        _run(tmp_path / "empty", tmp_path / "out")


def test_countries_and_scope():
    assert len(countries.get("PT").boxes) == 3
    fr = countries.get("FR")
    assert fr.drop_outside and "Overseas" in fr.excluded
    pkg = datapackage.build_package(fr, {"fr_climate_normals_1991_2020": pd.DataFrame({"code": ["01001"]})},
                                    daily=False, n_places=1, n_loaded=3)
    assert "Overseas" in pkg["description"] and "2 loaded places" in pkg["description"]
    places = pd.DataFrame({"code": ["97101", "75056"], "name": ["x", "Paris"],
                           "latitude": [16.2, 48.86], "longitude": [-61.5, 2.35]})
    parts = build.split_by_box(fr, places)
    assert len(parts) == 1 and parts[0][1].code.tolist() == ["75056"]
    with pytest.raises(ValueError):
        build.split_by_box(countries.get("LU"), places)


def test_altitude_adjustment(tmp_path):
    cache = tmp_path / "cache"
    mk.make(cache, "LU", dem_m=1000.0, cell_m=200.0)
    res = _run(cache, tmp_path / "out")
    a, b = res["A"], res["B"]
    assert (a.elevation_m == 1000).all() and (a.grid_elevation_m == 200).all()
    # 800 m above the cell: 0.0065 * 800 = 5.2 degC colder, rain unchanged
    for m in (1, 7):
        assert (a[a.month == m].tmean_c == round(11.0 + m - 5.2, 1)).all()
    assert (a[a.month == 1].precip_mm == 68.2).all()
    ann = b[b.month.astype(str) == "annual"]
    assert (ann.tmean_shift_c == 1.0).all()


def test_missing_dem_tile_keeps_cell_elevation(tmp_path):
    from climate_data import elevation

    cache = tmp_path / "cache"
    mk.make(cache, "LU", dem_m=1000.0, cell_m=200.0)
    for f in (cache / elevation.DEM_DIR).glob("*.tif"):
        f.unlink()
        f.with_name(f.name + ".missing").touch()  # as after a 404 (tile over sea)
    a = _run(cache, tmp_path / "out")["A"]
    assert (a.elevation_m == 200).all()
    assert (a[a.month == 1].tmean_c == 12.0).all()
