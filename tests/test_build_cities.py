import json
import zipfile

import numpy as np
import pandas as pd
import pytest

from climate_data import build_cities as bc
from climate_data.cities import OUTPUT_COLUMNS


def _zip(path, lat, lon, seed):
    t = pd.date_range("1990-12-31 00:00", "1994-01-01 23:00", freq="h", tz="UTC")
    rng = np.random.default_rng(seed)
    hour = t.hour.to_numpy()
    doy = t.day_of_year.to_numpy()
    t2m = 283.15 + 8 * np.sin(2 * np.pi * (doy - 110) / 365) + 4 * np.sin(2 * np.pi * (hour - 9) / 24)
    df = pd.DataFrame({
        "valid_time": t.strftime("%Y-%m-%d %H:%M:%S"),
        "latitude": lat, "longitude": lon,
        "t2m": t2m, "tp": rng.uniform(0, 0.0002, len(t)),
        "u10": rng.uniform(-5, 5, len(t)), "v10": rng.uniform(-5, 5, len(t)),
        "ssrd": np.where((hour > 6) & (hour < 18), 1.5e6, 0.0),
    })
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("data.csv", df.to_csv(index=False))


@pytest.fixture
def setup(tmp_path):
    cities = pd.DataFrame([
        ["GB", "2643743", "London", "London", "ENG", "England", 51.5085, -0.1257, 8961989, "Europe/London", 1],
        ["GB", "2655603", "Birmingham", "Birmingham", "ENG", "England", 52.4814, -1.8998, 984333, "Europe/London", 2],
        ["GB", "2643123", "Manchester", "Manchester", "ENG", "England", 53.4809, -2.2374, 395515, "Europe/London", 3],
    ], columns=OUTPUT_COLUMNS)
    cpath = tmp_path / "gb.csv"
    cities.to_csv(cpath, index=False)
    cache = tmp_path / "ts"
    (cache / "GB").mkdir(parents=True)
    _zip(cache / "GB" / "2643743.zip", 51.5, -0.1, 1)
    _zip(cache / "GB" / "2655603.zip", 52.5, -1.9, 2)
    pd.DataFrame({"city_id": ["2643743", "2655603", "2643123"], "req_lat": [0, 0, 0], "req_lon": [0, 0, 0],
                  "grid_lat": [51.5, 52.5, 53.5], "grid_lon": [-0.1, -1.9, -2.2],
                  "status": ["ok", "neighbour", "no_land"], "seconds": 1, "bytes": 1}
                 ).to_csv(cache / "GB" / "manifest.csv", index=False)
    return cpath, cache


def _elev(lats, lons, glats, glons):
    return np.full(len(lats), 20.0), np.full(len(lats), 120.0)


def test_build_writes_all_files(setup, tmp_path):
    cpath, cache = setup
    out = tmp_path / "out"
    rc = bc.main(["--country", "GB", "--cities", str(cpath), "--cache", str(cache), "--out", str(out),
                  "--urls", str(tmp_path / "none.csv"), "--min-days", "1000"], elevation_fn=_elev)
    assert rc == 0
    d = out / "GB"
    names = bc.file_names("GB")
    for n in names.values():
        assert (d / n).exists(), n

    c = pd.read_csv(d / names["cities"], dtype=str)
    assert list(c.columns) == bc.CITY_COLUMNS
    assert list(c["city_id"]) == ["2643743", "2655603"]  # no_land skipped
    assert set(c["elevation_m"].astype(float)) == {20.0}

    daily = pd.read_parquet(d / names["daily_parquet"])
    assert list(daily.columns) == ["country", "city_id", "name", "date", "tmean_c", "tmin_c", "tmax_c",
                                   "precip_mm", "wind_mean_kmh", "wind_max_kmh", "solar_kwh_m2"]
    assert daily.groupby("city_id").size().min() >= 1000
    # 100 m lower than the cell: +0.65 C vs the unadjusted mean (~10 C)
    assert 10.3 < daily["tmean_c"].mean() < 11.0

    with zipfile.ZipFile(d / names["daily_zip"]) as zf:
        assert sorted(zf.namelist()) == ["gb_birmingham_2655603_daily.csv", "gb_london_2643743_daily.csv"]
        one = pd.read_csv(zf.open("gb_london_2643743_daily.csv"))
    assert list(one.columns) == ["date", "tmean_c", "tmin_c", "tmax_c", "precip_mm", "wind_mean_kmh",
                                 "wind_max_kmh", "solar_kwh_m2"]

    m = pd.read_csv(d / names["monthly_csv"])
    assert list(m.columns) == ["country", "city_id", "name", "year", "month", "tmean_c", "tmin_mean_c",
                               "tmax_mean_c", "tmin_abs_c", "tmax_abs_c", "precip_mm", "wet_days", "frost_days",
                               "hdd_15_5", "hdd_18", "cdd_18", "cdd_22", "gtz_20_15", "solar_kwh_m2",
                               "wind_mean_kmh"]
    assert len(pd.read_parquet(d / names["monthly_parquet"])) == len(m)
    nm = pd.read_csv(d / names["normals"])
    assert list(nm.columns) == ["country", "city_id", "name", "month", "tmean_c", "tmin_c", "tmax_c", "precip_mm",
                                "wet_days", "frost_days", "summer_days", "hot_days", "solar_kwh_m2_day",
                                "wind_mean_kmh", "hdd_15_5", "hdd_18", "cdd_18"]
    assert len(nm) == 24
    a = pd.read_csv(d / names["annual"])
    assert list(a.columns) == ["country", "city_id", "name", "year", "tmean_c", "tmean_anomaly_c", "precip_mm",
                               "precip_anomaly_pct", "wet_days", "heavy_rain_days", "max_1day_precip_mm",
                               "frost_days", "ice_days", "summer_days", "hot_days", "tropical_nights",
                               "tmax_abs_c", "tmin_abs_c", "hdd_15_5", "hdd_18", "cdd_18", "cdd_22",
                               "rank_warmest"]
    assert sorted(a["year"].unique()) == [1991, 1992, 1993]

    pkg = json.loads((d / names["datapackage"]).read_text())
    assert pkg["licenses"][0]["name"] == "CC-BY-4.0"
    assert {r["path"] for r in pkg["resources"]} == set(names.values()) - {names["datapackage"]}
    titles = " ".join(s["title"] for s in pkg["sources"])
    assert "ERA5-Land hourly time series" in titles and "GeoNames" in titles and "Copernicus DEM" in titles
    daily_res = next(r for r in pkg["resources"] if r["path"] == names["daily_parquet"])
    assert [f["name"] for f in daily_res["schema"]["fields"]] == list(daily.columns)


def test_min_days_fails_run(setup, tmp_path, capsys):
    cpath, cache = setup
    rc = bc.main(["--country", "GB", "--cities", str(cpath), "--cache", str(cache), "--out", str(tmp_path / "o"),
                  "--urls", str(tmp_path / "none.csv")], elevation_fn=_elev)
    assert rc == 1
    assert "fewer than 27000 days" in capsys.readouterr().err
    assert not (tmp_path / "o" / "GB").exists()


def test_validate_catches_tmin_above_tmax():
    dates = pd.date_range("2000-01-01", periods=5).date
    d = pd.DataFrame({"country": "GB", "city_id": "1", "name": "X", "date": dates,
                      "tmean_c": 5.0, "tmin_c": 2.0, "tmax_c": 8.0, "precip_mm": 1.0})
    a = pd.DataFrame({"city_id": ["1"], "name": ["X"], "year": [2000], "precip_mm": [800.0]})
    assert bc.validate(d, a, min_days=5) == []
    d.loc[2, "tmin_c"] = 9.0
    errs = bc.validate(d, a, min_days=5)
    assert len(errs) == 1 and "tmin <= tmean <= tmax" in errs[0] and "2000-01-03" in errs[0]
    a.loc[0, "precip_mm"] = 50.0
    d.loc[3, "date"] = d.loc[4, "date"]
    errs = bc.validate(d, a, min_days=5)
    assert any("annual precipitation" in e for e in errs) and any("repeated" in e for e in errs)
