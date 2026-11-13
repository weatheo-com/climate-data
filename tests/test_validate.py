import json
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

from climate_data import build, validate

FIX = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(FIX))
import make_cds_fixture as mk  # noqa: E402

A = "lu_climate_normals_1991_2020"
B = "lu_climate_shift_1961_1990_vs_1991_2020"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    cache = tmp_path_factory.mktemp("cache")
    mk.make(cache, "LU")
    out = tmp_path_factory.mktemp("out")
    res = build.build("LU", cache, out, offline=True, places_path=FIX / "lu_places")
    return res["dir"]


def _copy(src: Path, tmp_path: Path) -> Path:
    d = tmp_path / "LU"
    shutil.copytree(src, d)
    return d


def _edit(d: Path, name: str, fn):
    f = d / f"{name}.csv"
    df = pd.read_csv(f, dtype=str, keep_default_na=False)
    df = fn(df)
    df.to_csv(f, index=False)
    df.to_parquet(f.with_suffix(".parquet"), index=False)  # keep the parquet twin in step


def test_valid_build_passes(built, capsys):
    assert validate.main([str(built / "datapackage.json")]) == 0
    assert "OK" in capsys.readouterr().out


def test_duplicate_and_hot_value_fail(built, tmp_path, capsys):
    d = _copy(built, tmp_path)

    def spoil(df):
        df.loc[0, "tmean_c"] = "99.0"
        return pd.concat([df, df.iloc[[5]]], ignore_index=True)

    _edit(d, A, spoil)
    assert validate.main([str(d / "datapackage.json")]) == 1
    out = capsys.readouterr().out
    assert "duplicate (code, month)" in out
    assert "tmean_c outside -30.0..35.0" in out and "tmean_c=99.0" in out
    assert "without exactly 12 rows" in out


def test_shift_rows_types_url_coords(built, tmp_path):
    d = _copy(built, tmp_path)
    _edit(d, B, lambda df: df[df["month"] != "annual"].reset_index(drop=True))

    def spoil_a(df):
        df.loc[0, "precip_mm"] = "abc"
        df.loc[1, "weatheo_url"] = "http://evil.example/x"
        df.loc[2, "latitude"] = "10.0"
        df.loc[3, "frost_days"] = "40" if "frost_days" in df else df.loc[3, "precip_mm"]
        return df

    _edit(d, A, spoil_a)
    probs = "\n".join(validate.validate(d / "datapackage.json"))
    assert "without exactly 13 rows" in probs
    assert "column precip_mm not number" in probs
    assert "weatheo_url neither empty" in probs
    assert "coordinates outside the LU boxes" in probs


def test_attribution_and_columns(built, tmp_path):
    d = _copy(built, tmp_path)
    pj = d / "datapackage.json"
    pkg = json.loads(pj.read_text())
    pkg["description"] = "no attribution"
    pj.write_text(json.dumps(pkg))
    _edit(d, A, lambda df: df.drop(columns=["period"]))
    probs = "\n".join(validate.validate(pj))
    assert "attribution text missing" in probs
    assert "missing ['period']" in probs


def test_annual_precip_allowed_above_monthly_cap(built, tmp_path):
    d = _copy(built, tmp_path)

    def wet(df):
        df.loc[df["month"] == "annual", "precip_1991_2020_mm"] = "2400.0"
        return df

    _edit(d, B, wet)
    assert validate.validate(d / "datapackage.json") == []
