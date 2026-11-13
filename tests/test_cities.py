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
    monkeypatch.setattr(cities, "read_official", lambda country: None)
    assert cities.main(["--country", "FR", "--top", "5", "--raw", str(raw), "--out", str(tmp_path / "out")]) == 0
    df = pd.read_csv(tmp_path / "out" / "fr.csv")
    assert list(df.columns) == OUTPUT_COLUMNS
    assert df["name"].tolist() == ["Paris"]
    assert df["admin1_name"].tolist() == ["Île-de-France"]


def _fr(gid, name, a4, pop, lat="48.85", lon="2.35"):
    r = _row(gid, name, "PPL", "FR", pop, admin1="11", tz="Europe/Paris")
    r.update(admin4_code=a4, latitude=lat, longitude=lon)
    return r


def test_one_per_municipality_official_names():
    df = pd.DataFrame([
        _fr(10, "Paris", "75056", 2_100_000),
        _fr(11, "Paris 15 Vaugirard", "75056", 230_000),
        _fr(12, "Gare", "75056", 75_000),
        _fr(13, "Marne La Vallée", "", 318_000),
        _fr(14, "Dunkirk", "59183", 86_000, lat="51.03", lon="2.37"),
        _fr(15, "Lyon", "69123", 520_000, lat="45.76", lon="4.83"),
    ], columns=GEONAMES_COLUMNS)
    official = pd.DataFrame({"code": ["75056", "59183", "69123"], "name": ["Paris", "Dunkerque", "Lyon"],
                             "population": [2_100_000, 87_000, 520_000]})
    out = select_cities(df, "FR", 10, official=official)
    assert out["name"].tolist() == ["Paris", "Lyon", "Dunkerque"]
    assert out["city_id"].tolist() == [10, 15, 14]
    assert out.loc[2, "population"] == 87_000


def test_same_cell_dropped_when_same_admin2():
    rows = [_row(1, "London", "PPLC", "GB", 9_000_000), _row(2, "City of Westminster", "PPLA3", "GB", 250_000),
            _row(3, "Croydon", "PPL", "GB", 190_000)]
    for r in rows:
        r["admin2_code"] = "GLA"
    rows[2]["latitude"] = "51.37"
    out = select_cities(pd.DataFrame(rows, columns=GEONAMES_COLUMNS), "GB", 10)
    assert out["name"].tolist() == ["London", "Croydon"]
