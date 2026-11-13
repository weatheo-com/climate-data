import datetime as dt
import zipfile

import numpy as np
import pandas as pd
import pytest

from climate_data.daily import read_timeseries_zip, to_daily

PARIS = "Europe/Paris"
D = dt.date


def hourly(start, end, t_c=10.0, tp=0.0, u=3.0, v=4.0, ssrd=3.6e5):
    idx = pd.date_range(start, end, freq="h", tz="UTC", name="valid_time")
    n = len(idx)
    return pd.DataFrame({"t2m": np.full(n, t_c + 273.15), "tp": np.full(n, tp),
                         "u10": np.full(n, u), "v10": np.full(n, v),
                         "ssrd": np.full(n, ssrd)}, index=idx)


def row(out, day):
    r = out[out["date"] == day]
    assert len(r) == 1, out
    return r.iloc[0]


def test_paris_boundary_and_incomplete_days_dropped():
    h = hourly("2024-01-01 00:00", "2024-01-04 00:00")
    h.loc[pd.Timestamp("2024-01-01 23:00", tz="UTC"), "t2m"] = 30 + 273.15  # local Jan 2 00:00
    h.loc[pd.Timestamp("2024-01-02 22:00", tz="UTC"), "t2m"] = -5 + 273.15  # local Jan 2 23:00
    out = to_daily(h, PARIS)
    # Jan 1 local starts Dec 31 23:00 UTC (missing); Jan 4 has 1 hour only.
    assert list(out["date"]) == [D(2024, 1, 2), D(2024, 1, 3)]
    a, b = row(out, D(2024, 1, 2)), row(out, D(2024, 1, 3))
    assert a["tmax_c"] == 30.0 and a["tmin_c"] == -5.0
    assert b["tmax_c"] == 10.0 and b["tmin_c"] == 10.0
    assert a["tmean_c"] == pytest.approx(round((22 * 10 + 30 - 5) / 24, 1))


def test_precip_hour_ending_shift_and_negative_clip():
    h = hourly("2024-01-01 00:00", "2024-01-04 00:00", tp=-1e-6)
    h.loc[pd.Timestamp("2024-01-02 23:00", tz="UTC"), "tp"] = 0.002  # hour ending local 00:00 Jan 3 -> Jan 2
    h.loc[pd.Timestamp("2024-01-03 00:00", tz="UTC"), "tp"] = 0.001  # hour ending local 01:00 Jan 3 -> Jan 3
    out = to_daily(h, PARIS)
    assert row(out, D(2024, 1, 2))["precip_mm"] == 2.0
    assert row(out, D(2024, 1, 3))["precip_mm"] == 1.0


def test_dst_spring_day_has_23_hours_and_is_kept():
    h = hourly("2024-03-30 00:00", "2024-04-02 00:00")
    out = to_daily(h, PARIS)
    assert D(2024, 3, 31) in set(out["date"])
    assert row(out, D(2024, 3, 31))["solar_kwh_m2"] == 2.3
    assert row(out, D(2024, 4, 1))["solar_kwh_m2"] == 2.4


def test_dst_autumn_day_has_25_hours():
    h = hourly("2024-10-26 00:00", "2024-10-29 00:00")
    out = to_daily(h, PARIS)
    assert row(out, D(2024, 10, 27))["solar_kwh_m2"] == 2.5


def test_units_and_offset():
    h = hourly("2024-06-01 00:00", "2024-06-04 00:00", t_c=20.0, tp=0.0005)
    out = to_daily(h, PARIS, temp_offset_c=-1.3)
    r = row(out, D(2024, 6, 2))
    assert r["tmean_c"] == 18.7 and r["tmin_c"] == 18.7 and r["tmax_c"] == 18.7
    assert r["precip_mm"] == 12.0
    assert r["wind_mean_kmh"] == 18.0 and r["wind_max_kmh"] == 18.0
    assert r["solar_kwh_m2"] == 2.4
    assert list(out.columns) == ["date", "tmean_c", "tmin_c", "tmax_c", "precip_mm",
                                 "wind_mean_kmh", "wind_max_kmh", "solar_kwh_m2"]


def test_gap_drops_day_for_each_convention():
    h = hourly("2024-01-01 00:00", "2024-01-05 00:00")
    h = h.drop(pd.Timestamp("2024-01-02 10:00", tz="UTC"))
    out = to_daily(h, PARIS)
    assert D(2024, 1, 2) not in set(out["date"])
    # Missing tp only at valid 2024-01-03 23:00 UTC -> amount day Jan 3, instantaneous day Jan 4.
    h2 = hourly("2024-01-01 00:00", "2024-01-05 00:00")
    h2.loc[pd.Timestamp("2024-01-03 23:00", tz="UTC"), "tp"] = np.nan
    days = set(to_daily(h2, PARIS)["date"])
    assert D(2024, 1, 3) not in days and D(2024, 1, 4) in days


def test_missing_variables_columns_left_out():
    h = hourly("2024-01-01 00:00", "2024-01-04 00:00")[["t2m", "tp"]]
    out = to_daily(h, PARIS)
    assert list(out.columns) == ["date", "tmean_c", "tmin_c", "tmax_c", "precip_mm"]
    assert len(out) == 2


def test_read_timeseries_zip(tmp_path):
    h = hourly("2024-01-01 00:00", "2024-01-04 00:00")
    t = h.index.tz_localize(None).strftime("%Y-%m-%d %H:%M:%S")
    p = tmp_path / "ts.zip"
    with zipfile.ZipFile(p, "w") as zf:
        for name, vs in (("a.csv", ["t2m", "u10", "v10"]), ("b.csv", ["tp", "ssrd"])):
            df = pd.DataFrame({"valid_time": t, **{v: h[v].to_numpy() for v in vs},
                               "latitude": 48.85, "longitude": 2.35})
            zf.writestr(name, df.to_csv(index=False))
    got, lat, lon = read_timeseries_zip(p)
    assert (lat, lon) == (48.85, 2.35)
    assert str(got.index.tz) == "UTC" and len(got) == len(h)
    assert set(got.columns) == {"t2m", "u10", "v10", "tp", "ssrd"}
    pd.testing.assert_frame_equal(to_daily(got, PARIS), to_daily(h, PARIS))
