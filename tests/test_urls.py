import pandas as pd

from climate_data.urls import join_urls, norm_name


def _places(rows, country="FR"):
    return pd.DataFrame([
        dict(country=country, code=c, name=n, admin1_code="", admin1_name="",
             admin2_code="", admin2_name="", latitude=la, longitude=lo)
        for c, n, la, lo in rows])


def _urls(rows, country="FR"):
    return pd.DataFrame([
        dict(country=country, code=c, name=n, admin1_name="",
             latitude=la, longitude=lo, path=p)
        for c, n, la, lo, p in rows])


def test_norm_name():
    assert norm_name("Saint-Étienne") == norm_name("saint etienne")
    assert norm_name("L’Haÿ-les-Roses") == norm_name("l'hay les roses")
    assert norm_name("Aranđelovac") == "arandelovac"


def test_exact_code_match_fr():
    p = _places([("01002", "L'Abergement", 46.0, 5.0)])
    u = _urls([("01002", "Totally Other", 50.0, 2.0, "/fr/ara/abergement")])
    out = join_urls(p, u, "FR")
    assert out.loc[0, "weatheo_url"] == "https://weatheo.com/fr/fr/ara/abergement"


def test_near_name_match_and_lang():
    p = _places([("0101", "Águeda", 40.57, -8.45)], "PT")
    u = _urls([("", "Agueda", 40.60, -8.44, "/pt/aveiro/agueda")], "PT")
    out = join_urls(p, u, "PT")
    assert out.loc[0, "weatheo_url"] == "https://weatheo.com/pt/pt/aveiro/agueda"


def test_same_name_far_away_no_match():
    # ~40 km north
    p = _places([("1", "Beograd", 44.80, 20.46)], "RS")
    u = _urls([("", "Beograd", 45.16, 20.46, "/rs/x/beograd")], "RS")
    out = join_urls(p, u, "RS")
    assert out.loc[0, "weatheo_url"] == ""


def test_closest_of_duplicates_by_place():
    # two places share a name, each gets its own nearby page
    p = _places([("1", "Bettendorf", 49.88, 6.22), ("2", "Bettendorf", 49.50, 6.00)], "LU")
    u = _urls([("", "Bettendorf", 49.881, 6.221, "/lu/a/bettendorf"),
               ("", "Bettendorf", 49.501, 6.001, "/lu/b/bettendorf")], "LU")
    out = join_urls(p, u, "LU")
    assert list(out["weatheo_url"]) == ["https://weatheo.com/fr/lu/a/bettendorf",
                                        "https://weatheo.com/fr/lu/b/bettendorf"]


def test_ambiguous_duplicate_urls_no_match():
    p = _places([("1", "Sainte-Marie", 45.0, 5.0)])
    u = _urls([("", "Sainte Marie", 45.01, 5.0, "/fr/a/sainte-marie"),
               ("", "Sainte Marie", 44.99, 5.0, "/fr/b/sainte-marie")])
    assert join_urls(p, u, "FR").loc[0, "weatheo_url"] == ""


def test_one_page_claimed_by_two_places_no_match():
    p = _places([("1", "Vila", 41.0, -8.0), ("2", "Vila", 41.02, -8.0)], "PT")
    u = _urls([("", "Vila", 41.01, -8.0, "/pt/x/vila")], "PT")
    assert list(join_urls(p, u, "PT")["weatheo_url"]) == ["", ""]
