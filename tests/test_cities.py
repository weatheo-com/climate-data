import pandas as pd
import pytest

from climate_data import cities
from climate_data.cities import GEONAMES_COLUMNS, OUTPUT_COLUMNS, select_cities


def _row(gid, name, code, cc, pop, admin1="ENG", tz="Europe/London"):
    r = dict.fromkeys(GEONAMES_COLUMNS, "")
    r.update(geonameid=str(gid), name=name, asciiname=name.replace("é", "e"), latitude="51.5",
             longitude="-0.1", feature_class="P", feature_code=code, country_code=cc,
             admin1_code=admin1, population=str(pop), timezone=tz)
    return r


@pytest.fixture
def frame():
    return pd.DataFrame([
        _row(1, "Smallville", "PPL", "GB", 6000),
        _row(2, "London", "PPLC", "GB", 8_900_000),
        _row(3, "Westminster", "PPLX", "GB", 9_000_000),  # section of city: dropped
        _row(4, "Edinburgh", "PPLA", "GB", 500_000, admin1="SCT"),
        _row(5, "Paris", "PPLC", "FR", 2_100_000, admin1="11", tz="Europe/Paris"),
        _row(6, "Leeds", "PPLA2", "GB", 790_000),
        _row(7, "Tie", "PPLA3", "GB", 6000),
    ], columns=GEONAMES_COLUMNS)


def test_ranking_and_filter(frame):
    out = select_cities(frame, "gb", 3, {"GB.ENG": "England", "GB.SCT": "Scotland"})
    assert list(out.columns) == OUTPUT_COLUMNS
    assert out["name"].tolist() == ["London", "Leeds", "Edinburgh"]
    assert out["rank"].tolist() == [1, 2, 3]
    assert out["city_id"].tolist() == [2, 6, 4]
    assert out["admin1_name"].tolist() == ["England", "England", "Scotland"]
    assert (out["country"] == "GB").all()
    assert out["timezone"].iloc[0] == "Europe/London"


def test_pplx_dropped_and_fewer_than_top(frame):
    out = select_cities(frame, "GB", 100)
    assert len(out) == 5
    assert "Westminster" not in out["name"].tolist()
    assert out["rank"].tolist() == [1, 2, 3, 4, 5]
    # population tie broken by geonameid
    assert out["city_id"].tolist()[-2:] == [1, 7]
    assert (out["admin1_name"] == "").all()


def test_bad_country(frame):
    with pytest.raises(ValueError):
        select_cities(frame, "US", 10)


def test_build_writes_csv(tmp_path, frame, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    frame.to_csv(raw / cities.CITIES_TXT, sep="\t", header=False, index=False)
    (raw / cities.ADMIN1_TXT).write_text("FR.11\tÎle-de-France\tIle-de-France\t3012874\n", encoding="utf-8")
    monkeypatch.setattr(cities, "_download", lambda url, dest: dest)
    assert cities.main(["--country", "FR", "--top", "5", "--raw", str(raw), "--out", str(tmp_path / "out")]) == 0
    df = pd.read_csv(tmp_path / "out" / "fr.csv")
    assert list(df.columns) == OUTPUT_COLUMNS
    assert df["name"].tolist() == ["Paris"]
    assert df["admin1_name"].tolist() == ["Île-de-France"]
