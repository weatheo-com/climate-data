import numpy as np
import pandas as pd
import pytest
import xarray as xr

from climate_data.normals import daily_normals, monthly_normals


def monthly_ds(years, tname="valid_time", t2m=283.15, tp=0.002):
    times = pd.date_range(f"{years[0]}-01-01", f"{years[-1]}-12-01", freq="MS")
    shape = (len(times), 2, 2)
    coords = {tname: times, "latitude": [49.6, 49.5], "longitude": [6.0, 6.1]}
    dims = (tname, "latitude", "longitude")
    return xr.Dataset(
        {"t2m": (dims, np.full(shape, t2m)), "tp": (dims, np.full(shape, tp))}, coords=coords
    )


def test_constant_temperature_and_feb_leap():
    out = monthly_normals(monthly_ds([2000]), 2000, 2000)
    assert list(out["month"].values) == list(range(1, 13))
    np.testing.assert_allclose(out["tmean_c"].values, 10.0)
    np.testing.assert_allclose(out["precip_mm"].sel(month=2).values, 58.0)
    np.testing.assert_allclose(out["precip_mm"].sel(month=1).values, 62.0)
    np.testing.assert_allclose(out["precip_mm"].sel(month=4).values, 60.0)


def test_leap_nonleap_mix_and_time_name():
    out = monthly_normals(monthly_ds([2000, 2001], tname="time"), 2000, 2001)
    np.testing.assert_allclose(out["precip_mm"].sel(month=2).values, 57.0)


def test_year_selection_and_missing_month():
    ds = monthly_ds([1999, 2000, 2001])
    ds["t2m"] = ds["t2m"] + xr.DataArray([0.0] * 12 + [1.0] * 12 + [3.0] * 12, dims="valid_time")
    out = monthly_normals(ds, 2000, 2001)
    np.testing.assert_allclose(out["tmean_c"].values, 12.0)
    with pytest.raises(ValueError):
        monthly_normals(ds.isel(valid_time=slice(0, 35)), 2000, 2001)
    with pytest.raises(ValueError):
        monthly_normals(ds, 2000, 2002)


def daily(years):
    times = pd.date_range(f"{years[0]}-01-01", f"{years[-1]}-12-31", freq="D")
    coords = {"time": times, "latitude": [49.6], "longitude": [6.0]}
    tmin = np.full((len(times), 1, 1), 273.15 + 5)
    tmax = np.full((len(times), 1, 1), 273.15 + 20)
    for i, t in enumerate(times):
        if t.year == 2001 and t.month == 1 and t.day <= 5:
            tmin[i] = 273.15 - 1
        if t.year == 2002 and t.month == 1 and t.day <= 3:
            tmin[i] = 273.15 - 1
        if t.year == 2002 and t.month == 1 and t.day == 4:
            tmin[i] = 273.15  # exactly 0 degC is not frost
        if t.year == 2001 and t.month == 7:
            tmax[i] = 273.15 + 26
        if t.year == 2002 and t.month == 8 and t.day == 1:
            tmax[i] = 273.15 + 25  # exactly 25 is a summer day
    dims = ("time", "latitude", "longitude")
    return xr.DataArray(tmax, coords=coords, dims=dims), xr.DataArray(tmin, coords=coords, dims=dims)


def test_daily_counts():
    tmax, tmin = daily([2001, 2002])
    out = daily_normals(tmax, tmin, 2001, 2002)
    assert out["frost_days"].sel(month=1).item() == pytest.approx(4.0)
    assert out["frost_days"].sel(month=2).item() == 0.0
    assert out["summer_days"].sel(month=7).item() == pytest.approx(15.5)
    assert out["summer_days"].sel(month=8).item() == pytest.approx(0.5)
    assert out["tmax_c"].sel(month=7).item() == pytest.approx(23.0)
    # Jan tmin: (5*-1 + 26*5) / 31 in 2001, (3*-1 + 0 + 27*5) / 31 in 2002, averaged over 62 days
    assert out["tmin_c"].sel(month=1).item() == pytest.approx((125 + 132) / 62)


def test_daily_missing_day_raises():
    tmax, tmin = daily([2001])
    with pytest.raises(ValueError):
        daily_normals(tmax.isel(time=slice(0, 364)), tmin.isel(time=slice(0, 364)), 2001, 2001)
