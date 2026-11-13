import numpy as np
import pandas as pd
import pytest

from climate_data.indicators import annual, monthly, normals, summary


def make_daily(start, end, tmean=10.0, tmin=None, tmax=None, precip=0.0, wind=True, solar=True):
    dates = pd.date_range(start, end, freq="D")
    n = len(dates)

    def arr(v):
        return np.asarray(v(dates) if callable(v) else np.full(n, v), dtype=float)

    t = arr(tmean)
    d = pd.DataFrame({
        "date": dates,
        "tmean_c": t,
        "tmin_c": arr(tmin) if tmin is not None else t - 5,
        "tmax_c": arr(tmax) if tmax is not None else t + 5,
        "precip_mm": arr(precip),
    })
    if wind:
        d["wind_mean_kmh"] = 12.0
        d["wind_max_kmh"] = 30.0
    if solar:
        d["solar_kwh_m2"] = 2.0
    return d


def test_monthly_drops_incomplete_month_and_degree_days():
    d = make_daily("2020-01-01", "2020-02-15", tmean=10.0)
    m = monthly(d)
    assert list(zip(m["year"], m["month"])) == [(2020, 1)]
    r = m.iloc[0]
    assert r["hdd_15_5"] == pytest.approx(31 * 5.5)
    assert r["hdd_18"] == pytest.approx(31 * 8)
    assert r["cdd_18"] == 0 and r["cdd_22"] == 0
    assert r["gtz_20_15"] == pytest.approx(31 * 10)
    assert r["solar_kwh_m2"] == pytest.approx(62.0)
    assert r["wind_mean_kmh"] == pytest.approx(12.0)
    assert r["tmin_abs_c"] == 5.0 and r["tmax_abs_c"] == 15.0


def test_monthly_thresholds_at_boundary():
    # precip alternates 1.0 (wet) and 0.99 (dry); tmin alternates 0.0 (not frost) and -0.1
    d = make_daily("2021-04-01", "2021-04-30", tmean=25.0,
                   precip=lambda ds: np.where(np.arange(len(ds)) % 2 == 0, 1.0, 0.99),
                   tmin=lambda ds: np.where(np.arange(len(ds)) % 2 == 0, 0.0, -0.1))
    r = monthly(d).iloc[0]
    assert r["wet_days"] == 15
    assert r["frost_days"] == 15
    assert r["cdd_18"] == pytest.approx(30 * 7)
    assert r["cdd_22"] == pytest.approx(30 * 3)
    assert r["gtz_20_15"] == 0
    assert r["hdd_15_5"] == 0


def test_monthly_omits_absent_columns():
    d = make_daily("2020-01-01", "2020-01-31", wind=False, solar=False)
    m = monthly(d)
    assert "solar_kwh_m2" not in m and "wind_mean_kmh" not in m


def test_annual_thresholds_and_incomplete_year():
    d = make_daily("2019-01-01", "2020-06-30", tmean=10.0)
    # 2019 boundary days
    idx = d["date"].dt.year == 2019
    d.loc[d.index[idx][:3], "tmax_c"] = [25.0, 30.0, -0.1]
    d.loc[d.index[idx][3:5], "tmin_c"] = [20.0, 19.9]
    d.loc[d.index[idx][5:8], "precip_mm"] = [20.0, 19.9, 1.0]
    a = annual(d, base=(2019, 2019))
    assert list(a["year"]) == [2019]
    r = a.iloc[0]
    assert r["summer_days"] == 2 and r["hot_days"] == 1 and r["ice_days"] == 1
    assert r["tropical_nights"] == 1
    assert r["heavy_rain_days"] == 1 and r["wet_days"] == 3
    assert r["max_1day_precip_mm"] == 20.0
    assert r["tmean_anomaly_c"] == 0 and r["precip_anomaly_pct"] == 0
    assert r["hdd_18"] == pytest.approx(365 * 8)
    assert r["rank_warmest"] == 1


def test_leap_year_complete():
    d = make_daily("2020-01-01", "2020-12-31")
    assert list(annual(d)["year"]) == [2020]
    assert list(annual(d.iloc[1:])["year"]) == []


def warming_daily():
    # tmean rises 0.02 C per year, constant within each year; precip varies by year
    def tmean(ds):
        return 8.0 + 0.02 * (ds.year - 1951)

    def precip(ds):
        return np.where(ds.year == 1990, 3.0, np.where(ds.year == 2000, 1.0, 2.0))
    return make_daily("1951-01-01", "2025-12-31", tmean=tmean, precip=precip)


def test_annual_anomaly_rank_and_summary_trend():
    d = warming_daily()
    a = annual(d)
    assert a["year"].min() == 1951 and a["year"].max() == 2025 and len(a) == 75
    base_mean = 8.0 + 0.02 * (2005.5 - 1951)
    r2025 = a[a["year"] == 2025].iloc[0]
    assert r2025["tmean_anomaly_c"] == pytest.approx(8.0 + 0.02 * 74 - base_mean, abs=0.06)
    assert r2025["rank_warmest"] == 1
    s = summary(a)
    assert s["trend_c_per_decade_1951_2025"] == pytest.approx(0.2, abs=0.01)
    assert s["trend_c_per_decade_1981_2025"] == pytest.approx(0.2, abs=0.02)
    assert s["warmest_year"] >= 2020 and s["coldest_year"] <= 1955
    assert s["wettest_year"] == 1990 and s["driest_year"] == 2000
    assert s["tmean_annual_c"] == pytest.approx(base_mean, abs=0.06)


def test_normals_twelve_rows():
    d = make_daily("1991-01-01", "2020-12-31", tmean=lambda ds: np.where(ds.month == 7, 22.0, 10.0),
                   tmax=lambda ds: np.where(ds.month == 7, 30.0, 15.0))
    n = normals(monthly(d), d)
    assert list(n["month"]) == list(range(1, 13))
    jul = n[n["month"] == 7].iloc[0]
    assert jul["tmean_c"] == 22.0 and jul["tmax_c"] == 30.0
    assert jul["summer_days"] == 31 and jul["hot_days"] == 31
    assert jul["cdd_18"] == pytest.approx(31 * 4)
    assert jul["solar_kwh_m2_day"] == pytest.approx(2.0)
    jan = n[n["month"] == 1].iloc[0]
    assert jan["summer_days"] == 0 and jan["hdd_15_5"] == pytest.approx(31 * 5.5)
    assert jan["wind_mean_kmh"] == 12.0
