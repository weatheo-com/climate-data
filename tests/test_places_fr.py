import logging
import time
from pathlib import Path

import pytest

from climate_data import places_fr

FIXTURE = Path(__file__).parent / "fixtures" / "fr_places.csv"
REAL = Path("/Users/neilocito/Desktop/WORK/1.site/weatheo data/used/FR/fr_rows (1).csv")


def test_fixture_loads_and_drops_empty_code(caplog):
    with caplog.at_level(logging.WARNING):
        df = places_fr.load(FIXTURE)
    assert len(df) == 20
    assert "dropped 1 rows" in caplog.text
    assert list(df.columns) == places_fr.COLUMNS
    assert (df["country"] == "FR").all()
    assert df["code"].is_unique
    assert df["code"].str.len().eq(5).all()
    assert "01002" in set(df["code"])  # leading zero restored
    row = df.set_index("code").loc["10002"]
    assert row["name"] == "Ailleville"
    assert row["admin1_code"] == "44" and row["admin1_name"] == "Grand Est"
    assert row["admin2_code"] == "10" and row["admin2_name"] == "Aube"
    # commune centre preferred over town hall
    assert row["latitude"] == pytest.approx(48.255)
    assert row["longitude"] == pytest.approx(4.694)


def test_centre_falls_back_to_mairie(tmp_path):
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    header = lines[0].split(",")
    i_lat, i_lon = header.index("latitude_centre"), header.index("longitude_centre")
    row = lines[1].split(",")  # 10002 Ailleville, no quoted fields
    row[i_lat] = row[i_lon] = ""
    p = tmp_path / "f.csv"
    p.write_text("\n".join([lines[0], ",".join(row)]) + "\n", encoding="utf-8")
    df = places_fr.load(p)
    assert df.loc[0, "latitude"] == pytest.approx(48.253)
    assert df.loc[0, "longitude"] == pytest.approx(4.682)


def test_duplicate_codes_raise(tmp_path):
    lines = FIXTURE.read_text(encoding="utf-8").splitlines()
    p = tmp_path / "dup.csv"
    p.write_text("\n".join([lines[0], lines[1], lines[1]]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicated"):
        places_fr.load(p)


@pytest.mark.skipif(not REAL.exists(), reason="real commune file not available")
def test_real_file():
    t = time.perf_counter()
    df = places_fr.load(REAL)
    assert time.perf_counter() - t < 10
    assert 34_800 <= len(df) <= 35_000
    assert df["code"].is_unique
    assert df["latitude"].between(-90, 90).all() and df["longitude"].between(-180, 180).all()
