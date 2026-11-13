"""Build a per-country city list (top N by population) from GeoNames cities5000.

Usage: python -m climate_data.cities --country GB --top 100 [--raw places/raw/geonames/] [--out places/cities/]

Downloads https://download.geonames.org/export/dump/cities5000.zip and admin1CodesASCII.txt once into
--raw, keeps populated places (PPLC, PPLA, PPLA2, PPLA3, PPLA4, PPL; not PPLX) of the country, sorts by
population descending and writes <out>/<cc>.csv. GeoNames data is CC BY 4.0.

France and Germany: GeoNames splits some cities into districts (Paris 15 Vaugirard, Gare) and lists
agglomerations that are not municipalities (Marne La Vallee). There each entry is mapped to its
municipality by admin4_code (INSEE code, AGS) and only one entry per municipality is kept; the name and
population come from the official table (INSEE communes, BKG VG250-EW), the point and time zone from
GeoNames (the entry named like the municipality, else the most populous one). Elsewhere an entry is
dropped when a more populous kept entry of the same admin2 lies in the same 0.1 deg cell (Westminster).
"""
from __future__ import annotations

import argparse
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

GEONAMES_BASE = "https://download.geonames.org/export/dump/"
CITIES_ZIP = "cities5000.zip"
CITIES_TXT = "cities5000.txt"
ADMIN1_TXT = "admin1CodesASCII.txt"

ALLOWED_COUNTRIES = ("GB", "DE", "FR", "PT", "LU", "RS")

# Names that are wrong in the official files used (communes-france-2026 names 93066 after the
# absorbed commune; the merged commune of 2025 is Saint-Denis).
NAME_FIXES = {"FR": {"93066": "Saint-Denis"}}

# Official municipality tables, joined to GeoNames admin4_code.
OFFICIAL = {
    "FR": {"path": Path("places/raw/fr/communes-france-2026.csv"), "code": "code_insee",
           "name": "nom_standard", "pop": "population", "filter": ("typecom", "COM")},
    "DE": {"path": Path("places/raw/de/de_gemeinden_vg250ew.csv"), "code": "ags", "name": "name", "pop": "pop"},
}
FEATURE_CODES = ("PPLC", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPL")

# Column layout of the GeoNames dump files (tab separated, no header).
GEONAMES_COLUMNS = [
    "geonameid", "name", "asciiname", "alternatenames", "latitude", "longitude",
    "feature_class", "feature_code", "country_code", "cc2", "admin1_code", "admin2_code",
    "admin3_code", "admin4_code", "population", "elevation", "dem", "timezone", "modification_date",
]
ADMIN1_COLUMNS = ["code", "name", "ascii_name", "geonameid"]

OUTPUT_COLUMNS = [
    "country", "city_id", "name", "ascii_name", "admin1_code", "admin1_name",
    "latitude", "longitude", "population", "timezone", "rank",
]


def _norm(name: str) -> str:
    import unicodedata

    n = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower()
    return "".join(ch for ch in n if ch.isalnum())


def read_official(country: str, path: Path | None = None) -> pd.DataFrame | None:
    """Official municipality table (code, name, population) of FR or DE; None for other countries
    or when the file is missing."""
    spec = OFFICIAL.get(country.upper())
    if spec is None:
        return None
    path = Path(path or spec["path"])
    if not path.exists():
        return None
    t = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    if "filter" in spec:
        col, val = spec["filter"]
        t = t[t[col] == val]
    out = pd.DataFrame({"code": t[spec["code"]].str.strip(), "name": t[spec["name"]],
                        "population": pd.to_numeric(t[spec["pop"]], errors="coerce").fillna(0).astype("int64")})
    for code, name in NAME_FIXES.get(country.upper(), {}).items():
        out.loc[out["code"] == code, "name"] = name
    return out[out["code"] != ""].drop_duplicates("code")


def one_per_municipality(sub: pd.DataFrame, official: pd.DataFrame) -> pd.DataFrame:
    """One GeoNames entry per municipality (admin4_code), with the official name and population.
    Entries without a known municipality code are dropped."""
    off = official.set_index("code")
    sub = sub[sub["admin4_code"].isin(off.index)].copy()
    if sub.empty:
        return sub
    sub["_match"] = [(_norm(n) == _norm(off.at[c, "name"])) or (_norm(a) == _norm(off.at[c, "name"]))
                     for n, a, c in zip(sub["name"], sub["asciiname"], sub["admin4_code"])]
    sub = sub.sort_values(["admin4_code", "_match", "population", "geonameid"],
                          ascending=[True, False, False, True], kind="mergesort")
    sub = sub.drop_duplicates("admin4_code", keep="first").drop(columns="_match")
    sub["name"] = [off.at[c, "name"] for c in sub["admin4_code"]]
    sub["asciiname"] = [_ascii(n) for n in sub["name"]]
    sub["population"] = [int(off.at[c, "population"]) for c in sub["admin4_code"]]
    return sub


def _ascii(name: str) -> str:
    import unicodedata

    return unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()


def drop_same_cell(sub: pd.DataFrame) -> pd.DataFrame:
    """Drop an entry when a more populous kept entry has the same non-empty admin2_code and the same
    0.1 deg cell. `sub` must be sorted by population descending."""
    seen: set[tuple] = set()
    keep = []
    for a2, la, lo in zip(sub["admin2_code"], sub["latitude"].astype(float), sub["longitude"].astype(float)):
        key = (a2, round(la * 10), round(lo * 10))
        if a2 and key in seen:
            keep.append(False)
            continue
        seen.add(key)
        keep.append(True)
    return sub[keep]


def select_cities(df: pd.DataFrame, country: str, top: int,
                  admin1: dict[str, str] | None = None,
                  official: pd.DataFrame | None = None) -> pd.DataFrame:
    """Top `top` populated places of `country` from a GeoNames-format frame (GEONAMES_COLUMNS).

    `admin1` maps "CC.code" -> admin1 name (from admin1CodesASCII.txt); missing names stay empty.
    Returns a frame with exactly OUTPUT_COLUMNS, rank 1..n by population descending
    (ties broken by geonameid ascending). Fewer rows than `top` is fine.
    """
    cc = country.upper()
    if cc not in ALLOWED_COUNTRIES:
        raise ValueError(f"country {country!r} not in {ALLOWED_COUNTRIES}")
    if top < 1:
        raise ValueError("top must be >= 1")
    admin1 = admin1 or {}

    sub = df[(df["country_code"] == cc) & (df["feature_code"].isin(FEATURE_CODES))].copy()
    sub["population"] = pd.to_numeric(sub["population"], errors="coerce").fillna(0).astype("int64")
    sub["geonameid"] = sub["geonameid"].astype("int64")
    if official is not None:
        sub = one_per_municipality(sub, official)
    sub = sub.sort_values(["population", "geonameid"], ascending=[False, True], kind="mergesort")
    if official is None:
        sub = drop_same_cell(sub)
    sub = sub.head(top)

    a1 = sub["admin1_code"].fillna("").astype(str)
    out = pd.DataFrame({
        "country": cc,
        "city_id": sub["geonameid"].to_numpy(),
        "name": sub["name"].to_numpy(),
        "ascii_name": sub["asciiname"].to_numpy(),
        "admin1_code": a1.to_numpy(),
        "admin1_name": [admin1.get(f"{cc}.{c}", "") for c in a1],
        "latitude": sub["latitude"].astype(float).to_numpy(),
        "longitude": sub["longitude"].astype(float).to_numpy(),
        "population": sub["population"].to_numpy(),
        "timezone": sub["timezone"].to_numpy(),
    })
    out["rank"] = range(1, len(out) + 1)
    return out[OUTPUT_COLUMNS].reset_index(drop=True)


def _download(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "climate-data/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    tmp.replace(dest)
    return dest


def fetch_geonames(raw: Path) -> tuple[Path, Path]:
    """Download cities5000.zip (extracted) and admin1CodesASCII.txt into `raw` once. Returns their paths."""
    raw = Path(raw)
    txt = raw / CITIES_TXT
    if not txt.exists():
        z = _download(GEONAMES_BASE + CITIES_ZIP, raw / CITIES_ZIP)
        with zipfile.ZipFile(z) as zf:
            zf.extract(CITIES_TXT, raw)
    a1 = _download(GEONAMES_BASE + ADMIN1_TXT, raw / ADMIN1_TXT)
    return txt, a1


def read_geonames(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t", header=None, names=GEONAMES_COLUMNS, dtype=str,
                       keep_default_na=False, quoting=3, encoding="utf-8")


def read_admin1(path: Path) -> dict[str, str]:
    a = pd.read_csv(path, sep="\t", header=None, names=ADMIN1_COLUMNS, dtype=str,
                    keep_default_na=False, quoting=3, encoding="utf-8")
    return dict(zip(a["code"], a["name"]))


def build(country: str, top: int, raw: Path, out: Path) -> Path:
    txt, a1 = fetch_geonames(raw)
    cities = select_cities(read_geonames(txt), country, top, read_admin1(a1), read_official(country))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / f"{country.lower()}.csv"
    cities.to_csv(dest, index=False, encoding="utf-8")
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m climate_data.cities", description=__doc__.splitlines()[0])
    ap.add_argument("--country", required=True, type=str.upper, choices=ALLOWED_COUNTRIES)
    ap.add_argument("--top", type=int, default=100)
    ap.add_argument("--raw", type=Path, default=Path("places/raw/geonames"))
    ap.add_argument("--out", type=Path, default=Path("places/cities"))
    a = ap.parse_args(argv)
    dest = build(a.country, a.top, a.raw, a.out)
    n = sum(1 for _ in open(dest, encoding="utf-8")) - 1
    print(f"wrote {dest} ({n} cities)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
