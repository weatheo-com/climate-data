"""Build a per-country city list (top N by population) from GeoNames cities5000.

Usage: python -m climate_data.cities --country GB --top 100 [--raw places/raw/geonames/] [--out places/cities/]

Downloads https://download.geonames.org/export/dump/cities5000.zip and admin1CodesASCII.txt once into
--raw, keeps populated places (PPLC, PPLA, PPLA2, PPLA3, PPLA4, PPL; not PPLX) of the country, sorts by
population descending and writes <out>/<cc>.csv. GeoNames data is CC BY 4.0.
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


def select_cities(df: pd.DataFrame, country: str, top: int,
                  admin1: dict[str, str] | None = None) -> pd.DataFrame:
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
    sub = sub.sort_values(["population", "geonameid"], ascending=[False, True], kind="mergesort").head(top)

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
    cities = select_cities(read_geonames(txt), country, top, read_admin1(a1))
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
