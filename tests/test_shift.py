import math

import pandas as pd
import pytest

from climate_data.shift import compute_shift


def table(tmean, precip, extra=None, code="01001"):
    rows = []
    for m in range(1, 13):
        r = {"country": "FR", "code": code, "name": "Abergement", "admin1_code": "84",
             "admin1_name": "ARA", "admin2_code": "01", "admin2_name": "Ain", "month": m,
             "tmean_c": tmean(m), "precip_mm": precip(m), "weatheo_url": "https://weatheo.com/x"}
        if extra:
            r.update({k: f(m) for k, f in extra.items()})
        rows.append(r)
    return pd.DataFrame(rows)


def test_basic_shift_and_annual():
    old = table(lambda m: float(m), lambda m: 50.0)
    new = table(lambda m: m + 1.0, lambda m: 55.0 if m != 3 else 0.0)
    out = compute_shift(old, new)
    assert list(out["month"]) == [str(i) for i in range(1, 13)] + ["annual"]
    jan = out[out.month == "1"].iloc[0]
    assert jan.tmean_1961_1990_c == 1.0 and jan.tmean_1991_2020_c == 2.0 and jan.tmean_shift_c == 1.0
    assert jan.precip_shift_pct == 10.0
    ann = out[out.month == "annual"].iloc[0]
    assert ann.tmean_1961_1990_c == 6.5 and ann.tmean_shift_c == 1.0
    assert ann.precip_1961_1990_mm == 600.0 and ann.precip_1991_2020_mm == 605.0
    assert ann.precip_shift_pct == pytest.approx(0.8)
    assert out.columns[0] == "country" and out.columns[-1] == "weatheo_url"
    assert out[out.month == "3"].iloc[0].precip_shift_pct == -100.0


def test_zero_old_precip_is_empty():
    old = table(lambda m: 5.0, lambda m: 0.0)
    new = table(lambda m: 5.0, lambda m: 3.0)
    out = compute_shift(old, new)
    assert all(math.isnan(v) for v in out["precip_shift_pct"])


def test_daily_columns():
    ex_old = {"tmax_c": lambda m: 10.0, "tmin_c": lambda m: 0.0, "frost_days": lambda m: 2.0, "summer_days": lambda m: 1.0}
    ex_new = {"tmax_c": lambda m: 11.0, "tmin_c": lambda m: 1.0, "frost_days": lambda m: 1.5, "summer_days": lambda m: 2.0}
    out = compute_shift(table(lambda m: 1.0, lambda m: 1.0, ex_old), table(lambda m: 1.0, lambda m: 1.0, ex_new))
    ann = out[out.month == "annual"].iloc[0]
    assert ann.tmax_shift_c == 1.0 and ann.tmin_1991_2020_c == 1.0
    assert ann.frost_days_1961_1990 == 24.0 and ann.frost_days_shift == -6.0
    assert ann.summer_days_shift == 12.0


def test_missing_month_raises():
    old = table(lambda m: 1.0, lambda m: 1.0)
    with pytest.raises(ValueError):
        compute_shift(old.iloc[:11], old)
