from pathlib import Path

import pytest

from climate_data import places_generic as pg

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).resolve().parent / "fixtures"
RAW = ROOT / "places" / "raw"


def _check(df, cc):
    assert list(df.columns) == pg.COLUMNS
    assert (df["country"] == cc).all()
    assert df["code"].is_unique
    assert df["code"].map(type).eq(str).all()
    lat0, lat1, lon0, lon1 = pg.BBOX[cc]
    assert df["latitude"].between(lat0, lat1).all()
    assert df["longitude"].between(lon0, lon1).all()
    assert df["name"].str.len().gt(0).all()


def test_pt_fixture():
    df = pg.load("PT", FIX / "pt_places.csv")
    _check(df, "PT")
    assert len(df) == 10
    r = df.set_index("code").loc["0101"]
    assert r["name"] == "Águeda" and r["admin1_code"] == "01" and r["admin1_name"] == "Aveiro"
    assert r["latitude"] == pytest.approx(40.595096464324)
    assert r["longitude"] == pytest.approx(-8.41615509152268)
    assert df.set_index("code").loc["4101", "admin1_name"] == "Ilha de Santa Maria"


def test_lu_fixture():
    df = pg.load("LU", FIX / "lu_places")
    _check(df, "LU")
    assert len(df) == 10
    s = df.set_index("code")
    assert s.loc["0101", "name"] == "Dippach" and s.loc["0101", "admin1_name"] == "Capellen"
    assert s.loc["0101", "latitude"] == pytest.approx(49.58833)
    # merged commune = mean of Hobscheid and Septfontaines
    assert s.loc["0103", "latitude"] == pytest.approx((49.68861 + 49.70111) / 2)
    assert s.loc["0103", "longitude"] == pytest.approx((5.91472 + 5.96722) / 2)
    # alias to "Ville de Luxembourg"; canton join keeps Wiltz commune off the canton point
    assert s.loc["0304", "latitude"] == pytest.approx(49.6093)
    assert s.loc["0807", "longitude"] == pytest.approx(5.9398)


def test_rs_fixture():
    df = pg.load("RS", FIX / "rs_places")
    _check(df, "RS")
    s = df.set_index("code")
    # abroad, prisons, city total (Grad Niš) and Kosovo dropped
    assert set(s.index) == {"70017", "70025", "70149", "71307", "71323", "71366", "80373"}
    assert s.loc["70017", "name"] == "Aleksandrovac"
    assert s.loc["70017", "admin2_code"] == "RS216" and s.loc["70017", "admin1_code"] == "RS21"
    assert s.loc["70149", "latitude"] == pytest.approx(44.77404)      # Beograd-Zvezdara
    assert s.loc["71323", "latitude"] == pytest.approx(43.30163)      # Niš-Palilula, not Beograd
    assert s.loc["71307", "longitude"] == pytest.approx(21.92356)     # Niš-Pantelej alias
    assert s.loc["71366", "latitude"] == pytest.approx(43.8496)       # Sevojno seat fallback
    assert s.loc["80373", "admin1_name"] == "Region Vojvodine"


def test_unmatched_raises(tmp_path):
    (tmp_path / "opshtine_sifops.csv").write_text(
        "idjezik,MBOPS,nOPS,IDNSTJ\n1,70017,Непознато,RS216\n", encoding="utf-8")
    (tmp_path / "RS.txt").write_text("", encoding="utf-8")
    with pytest.raises(pg.UnmatchedPlaces):
        pg.load("RS", tmp_path)
    assert len(pg.load("RS", tmp_path, strict=False)) == 0


def test_unknown_country():
    with pytest.raises(ValueError):
        pg.load("XX", FIX)


@pytest.mark.skipif(not RAW.exists(), reason="raw places files not downloaded")
@pytest.mark.parametrize("cc,lo,hi", [("PT", 308, 308), ("LU", 100, 100), ("RS", 145, 175)])
def test_real_files(cc, lo, hi):
    df = pg.load(cc, RAW / cc.lower())
    print(f"{cc}: {len(df)} places")
    _check(df, cc)
    assert lo <= len(df) <= hi


def test_pt_seats_prefers_seat_then_same_name():
    import pandas as pd

    from climate_data.places_generic import GEONAMES_COLS, pt_seats

    def row(name, code, admin2, lat, pop="0"):
        r = dict.fromkeys(GEONAMES_COLS, "")
        r.update(name=name, feature_class="P", feature_code=code, admin2=admin2,
                 latitude=lat, longitude=-9.0, population=pop)
        return r

    g = pd.DataFrame([
        row("Hill Village", "PPL", "3103", 32.70),
        row("Funchal", "PPLA", "3103", 32.65),       # seat wins
        row("Angra do Heroísmo", "PPL", "4301", 38.65, "100"),  # no seat: same-name place
        row("Angra do Heroismo", "PPL", "4301", 38.70, "5"),
        row("Elsewhere", "PPL", "9999", 40.0),
    ])
    out = pt_seats(g, pd.Series(["3103", "4301", "0101"]),
                   pd.Series(["Funchal", "Angra do Heroísmo", "Águeda"])).set_index("code")
    assert out.loc["3103", "latitude"] == 32.65
    assert out.loc["4301", "latitude"] == 38.65
    assert "0101" not in out.index
