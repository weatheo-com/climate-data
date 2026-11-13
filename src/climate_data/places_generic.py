"""Municipality loaders for PT, LU and RS (one small adapter per country).

load(country, path_or_dir) -> places DataFrame with the contract columns:
country, code, name, admin1_code, admin1_name, admin2_code, admin2_name,
latitude, longitude. Official codes stay strings with their leading zeros.

Sources (files under places/raw/<cc>/):
- PT: DGT CAOP 2025 municipalities (CC BY), one point inside each polygon
  (ST_PointOnSurface), file municipios_caop2025_pointonsurface.csv.
- LU: STATEC LAU codes (CC0), A1106.xlsx sheet "LU_SEP 2023"; coordinates from
  GeoNames LU.txt (CC BY 4.0) ADM2 features joined by normalised name within
  the canton. Communes merged after GeoNames' last update take the mean of
  their former communes' points (LU_ALIASES).
- RS: RZS SIFOPS list of municipalities and cities (opshtine_sifops.csv);
  coordinates from GeoNames RS.txt ADM3 features joined by normalised Latin
  name within the same GeoNames region (Vojvodina / rest of Serbia). City
  totals (Grad Beograd, Grad Niš, ...), Kosovo (90xxx, not in RS.txt) and
  non-territorial entries (abroad, prisons) are dropped; Belgrade and Niš
  city municipalities are kept as their own units.

Unmatched municipalities are never given invented coordinates: load() raises
with the list unless strict=False, in which case they are dropped and listed
in df.attrs["unmatched"].
"""
from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pandas as pd

COLUMNS = [
    "country", "code", "name", "admin1_code", "admin1_name",
    "admin2_code", "admin2_name", "latitude", "longitude",
]

# Rough country boxes (lat_min, lat_max, lon_min, lon_max) used as a sanity check.
BBOX = {
    "PT": (32.0, 42.2, -31.4, -6.1),  # Continente + Madeira + Azores
    "LU": (49.4, 50.2, 5.7, 6.6),
    "RS": (41.8, 46.2, 18.8, 23.1),
}

GEONAMES_COLS = [
    "geonameid", "name", "asciiname", "alternatenames", "latitude", "longitude",
    "feature_class", "feature_code", "country_code", "cc2", "admin1", "admin2",
    "admin3", "admin4", "population", "elevation", "dem", "timezone", "modified",
]


class UnmatchedPlaces(ValueError):
    pass


# --------------------------------------------------------------------------- helpers

def norm(s: str) -> str:
    """Casefolded name without accents, punctuation or repeated spaces."""
    s = str(s).replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def _clean(s) -> str:
    """Strip stray spaces and leading dashes from a label."""
    return re.sub(r"\s+", " ", str(s)).strip().lstrip("-").strip()


def _resolve(path_or_dir, filename: str) -> Path:
    p = Path(path_or_dir)
    return p / filename if p.is_dir() else p


def read_geonames(path: Path) -> pd.DataFrame:
    if Path(path).stat().st_size == 0:
        return pd.DataFrame({c: pd.Series(dtype=float if c in ("latitude", "longitude")
                                          else str) for c in GEONAMES_COLS})
    df = pd.read_csv(path, sep="\t", header=None, names=GEONAMES_COLS,
                     dtype=str, keep_default_na=False, quoting=3)
    df["latitude"] = df["latitude"].astype(float)
    df["longitude"] = df["longitude"].astype(float)
    return df


def _finish(df: pd.DataFrame, country: str, unmatched: list[str],
            strict: bool) -> pd.DataFrame:
    if unmatched and strict:
        raise UnmatchedPlaces(f"{country}: {len(unmatched)} unmatched: {unmatched}")
    df = df.dropna(subset=["latitude", "longitude"]).copy()
    df["country"] = country
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = ""
    df = df[COLUMNS].sort_values("code").reset_index(drop=True)
    if df["code"].duplicated().any():
        dups = df.loc[df["code"].duplicated(), "code"].tolist()
        raise ValueError(f"{country}: duplicate codes {dups}")
    df.attrs["unmatched"] = unmatched
    return df


# --------------------------------------------------------------------------- xlsx (no openpyxl)

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def read_xlsx_sheet(path: Path, sheet: str, max_empty: int = 50) -> list[list[str]]:
    """Rows of one sheet as lists of strings (columns A.. in order).

    Stops after max_empty consecutive empty rows (A1106.xlsx pads to 65531).
    """
    with zipfile.ZipFile(path) as z:
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rid = next(s.get(_RNS) for s in wb.iter(f"{{{_NS['m']}}}sheet")
                   if s.get("name") == sheet)
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        target = next(r.get("Target") for r in rels if r.get("Id") == rid)
        target = "xl/" + target.lstrip("/").removeprefix("xl/")
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", _NS):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{_NS['m']}}}t")))
        rows: list[list[str]] = []
        empty = 0
        with z.open(target) as fh:
            for _, el in ET.iterparse(fh):
                if el.tag != f"{{{_NS['m']}}}row":
                    continue
                cells: dict[int, str] = {}
                for c in el.findall("m:c", _NS):
                    col = re.match(r"[A-Z]+", c.get("r")).group()
                    idx = 0
                    for ch in col:
                        idx = idx * 26 + ord(ch) - 64
                    t = c.get("t")
                    if t == "s":
                        v = c.find("m:v", _NS)
                        val = shared[int(v.text)] if v is not None else ""
                    elif t == "inlineStr":
                        val = "".join(x.text or "" for x in c.iter(f"{{{_NS['m']}}}t"))
                    else:
                        v = c.find("m:v", _NS)
                        val = v.text if v is not None and v.text else ""
                    cells[idx - 1] = val
                el.clear()
                if not any(str(v).strip() for v in cells.values()):
                    empty += 1
                    if empty >= max_empty:
                        break
                    continue
                empty = 0
                width = max(cells) + 1
                rows.append([cells.get(i, "") for i in range(width)])
        return rows


# --------------------------------------------------------------------------- PT

def load_pt(path_or_dir, strict: bool = True) -> pd.DataFrame:
    path = _resolve(path_or_dir, "municipios_caop2025_pointonsurface.csv")
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    df = pd.DataFrame({
        "code": raw["dtmn"].str.strip().str.zfill(4),
        "name": raw["municipio"].map(_clean),
        # DICO = DD (district or island) + MM (municipality)
        "admin1_code": raw["dtmn"].str.strip().str.zfill(4).str[:2],
        "admin1_name": raw["distrito_ilha"].map(_clean),
        "latitude": pd.to_numeric(raw["Y"]),
        "longitude": pd.to_numeric(raw["X"]),
    })
    return _finish(df, "PT", [], strict)


# --------------------------------------------------------------------------- LU

# Communes (STATEC name, normalised) -> GeoNames ADM2 names (normalised) to use.
# Several entries: commune formed by a merger; its point is the mean of them.
LU_ALIASES = {
    "luxembourg": ["ville de luxembourg"],
    "colmar berg": ["berg"],
    "erpeldange sur sure": ["erpeldange"],
    "vallee de l ernz": ["commune de la vallee de l ernz"],
    "preizerdaul": ["commune de preizerdaul"],
    "redange attert": ["redange sur attert"],
    "habscht": ["hobscheid", "septfontaines"],
    "helperknapp": ["boevange sur attert", "tuntange"],
    "groussbus wal": ["grosbous", "wahl"],
    "rosport mompach": ["rosport", "mompach"],
    "bous waldbredimus": ["bous", "waldbredimus"],
}

# GeoNames admin1 code of each canton (LAU1 code from STATEC).
LU_CANTON_GEONAMES = {
    "01": "CA", "02": "ES", "03": "LU", "04": "ME", "05": "CL", "06": "DI",
    "07": "RD", "08": "WI", "09": "VD", "10": "EC", "11": "GR", "12": "RM",
}


def read_lu_communes(path: Path) -> pd.DataFrame:
    rows = read_xlsx_sheet(path, "LU_SEP 2023")
    out = []
    for r in rows:
        r = [_clean(x) for x in r] + [""] * 5
        if re.fullmatch(r"\d{1,2}", r[1]) and re.fullmatch(r"\d{3,4}", r[3]):
            out.append({"admin1_code": r[1].zfill(2), "admin1_name": r[2],
                        "code": r[3].zfill(4), "name": r[4]})
    return pd.DataFrame(out)


def load_lu(path_or_dir, strict: bool = True) -> pd.DataFrame:
    d = Path(path_or_dir)
    communes = read_lu_communes(d / "A1106.xlsx")
    gn = read_geonames(d / "LU.txt")
    adm2 = gn[gn["feature_code"] == "ADM2"]
    by_key: dict[tuple[str, str], list[tuple[float, float]]] = {}
    for _, g in adm2.iterrows():
        by_key.setdefault((g["admin1"], norm(g["name"])), []).append(
            (g["latitude"], g["longitude"]))
    lats, lons, unmatched = [], [], []
    for _, c in communes.iterrows():
        canton = LU_CANTON_GEONAMES.get(c["admin1_code"], "")
        key = norm(c["name"])
        names = LU_ALIASES.get(key, [key])
        pts = []
        for n in names:
            hit = by_key.get((canton, n), [])
            if len(hit) != 1:
                pts = []
                break
            pts.append(hit[0])
        if pts:
            lats.append(sum(p[0] for p in pts) / len(pts))
            lons.append(sum(p[1] for p in pts) / len(pts))
        else:
            lats.append(None)
            lons.append(None)
            unmatched.append(f"{c['code']} {c['name']}")
    communes["latitude"] = pd.to_numeric(pd.Series(lats, dtype=object))
    communes["longitude"] = pd.to_numeric(pd.Series(lons, dtype=object))
    return _finish(communes, "LU", unmatched, strict)


# --------------------------------------------------------------------------- RS

_CYR = dict(zip(
    "абвгдђежзијклљмнњопрстћуфхцчџшАБВГДЂЕЖЗИЈКЛЉМНЊОПРСТЋУФХЦЧЏШ",
    ["a", "b", "v", "g", "d", "đ", "e", "ž", "z", "i", "j", "k", "l", "lj", "m",
     "n", "nj", "o", "p", "r", "s", "t", "ć", "u", "f", "h", "c", "č", "dž", "š",
     "A", "B", "V", "G", "D", "Đ", "E", "Ž", "Z", "I", "J", "K", "L", "Lj", "M",
     "N", "Nj", "O", "P", "R", "S", "T", "Ć", "U", "F", "H", "C", "Č", "Dž", "Š"],
))


def cyr_to_lat(s: str) -> str:
    """Serbian Cyrillic to Serbian Latin (official one-to-one mapping)."""
    return "".join(_CYR.get(ch, ch) for ch in str(s))


# NUTS 2024 levels for Serbia: NUTS2 regions (admin1) and NUTS3 areas (admin2).
RS_NUTS2 = {
    "RS11": "Beogradski region",
    "RS12": "Region Vojvodine",
    "RS21": "Region Šumadije i Zapadne Srbije",
    "RS22": "Region Južne i Istočne Srbije",
}
RS_NUTS3 = {
    "RS110": "Beogradska oblast",
    "RS121": "Zapadnobačka oblast", "RS122": "Južnobanatska oblast",
    "RS123": "Južnobačka oblast", "RS124": "Severnobanatska oblast",
    "RS125": "Severnobačka oblast", "RS126": "Srednjobanatska oblast",
    "RS127": "Sremska oblast",
    "RS211": "Zlatiborska oblast", "RS212": "Kolubarska oblast",
    "RS213": "Mačvanska oblast", "RS214": "Moravička oblast",
    "RS215": "Pomoravska oblast", "RS216": "Rasinska oblast",
    "RS217": "Raška oblast", "RS218": "Šumadijska oblast",
    "RS221": "Borska oblast", "RS222": "Braničevska oblast",
    "RS223": "Zaječarska oblast", "RS224": "Jablanička oblast",
    "RS225": "Nišavska oblast", "RS226": "Pirotska oblast",
    "RS227": "Podunavska oblast", "RS228": "Pčinjska oblast",
    "RS229": "Toplička oblast",
}

# RZS normalised Latin name -> GeoNames normalised ADM3 key, where they differ.
RS_ALIASES: dict[str, str] = {
    # Niš city municipalities: GeoNames names them "Opština Niš-<name>".
    "pantelej": "nis pantelej",
    "crveni krst": "nis crveni krst",
    "medijana": "nis medijana",
}

# City municipalities with no GeoNames ADM3 polygon point: use the GeoNames
# populated place (the town that forms the unit) of the same name instead.
RS_SEAT_FALLBACK = {"sevojno"}


def _rs_key(name: str) -> str:
    """Normalised key for a Serbian municipality name (either source)."""
    k = norm(name)
    k = re.sub(r"^(opstina|grad|gradska opstina) ", "", k)
    k = re.sub(r" grad$", "", k)
    return k


def _rs_rzs_key(name: str, nuts3: str) -> str:
    lat = cyr_to_lat(name)
    m = re.match(r"^(.*?)\s*\((.*)\)\s*$", lat)
    if m:  # "Палилула (Београд)" -> "beograd palilula"
        return _rs_key(f"{m.group(2)} {m.group(1)}")
    k = _rs_key(lat)
    if nuts3 == "RS110" and k not in ("beograd",):
        k = "beograd " + k
    return RS_ALIASES.get(k, k)


def load_rs(path_or_dir, strict: bool = True) -> pd.DataFrame:
    d = Path(path_or_dir)
    raw = pd.read_csv(d / "opshtine_sifops.csv", dtype=str, keep_default_na=False,
                      encoding="utf-8-sig")
    raw = raw.rename(columns=lambda c: c.strip())
    raw["MBOPS"] = raw["MBOPS"].str.strip()
    raw["IDNSTJ"] = raw["IDNSTJ"].str.strip()
    # 70xxx/71xxx: municipalities, cities and city municipalities (Central Serbia)
    # 80xxx: Vojvodina. Dropped: 79xxx/89xxx city totals, 90xxx Kosovo,
    # 33xxx abroad, 55xxx prisons.
    keep = raw["MBOPS"].str.match(r"^(70|71|80)\d{3}$") & (raw["IDNSTJ"] != "")
    raw = raw[keep]
    gn = read_geonames(d / "RS.txt")
    adm3 = gn[gn["feature_code"] == "ADM3"]
    by_key: dict[tuple[str, str], list[tuple[float, float]]] = {}
    for _, g in adm3.iterrows():
        by_key.setdefault((g["admin1"], _rs_key(g["name"])), []).append(
            (g["latitude"], g["longitude"]))
    ppl = gn[gn["feature_class"] == "P"]
    seats: dict[tuple[str, str], list[tuple[float, float]]] = {}
    for _, g in ppl[ppl["name"].map(norm).isin(RS_SEAT_FALLBACK)].iterrows():
        seats.setdefault((g["admin1"], norm(g["name"])), []).append(
            (g["latitude"], g["longitude"]))
    rows, unmatched = [], []
    for _, r in raw.iterrows():
        nuts3 = r["IDNSTJ"]
        region = "VO" if nuts3.startswith("RS12") else "SE"
        key = _rs_rzs_key(r["nOPS"], nuts3)
        hit = by_key.get((region, key), [])
        if not hit and key in RS_SEAT_FALLBACK:
            hit = seats.get((region, key), [])
        lat = lon = None
        if len(hit) == 1:
            lat, lon = hit[0]
        else:
            unmatched.append(f"{r['MBOPS']} {cyr_to_lat(_clean(r['nOPS']))} -> {key!r}")
        rows.append({
            "code": r["MBOPS"],
            "name": cyr_to_lat(_clean(r["nOPS"])),
            "admin1_code": nuts3[:4], "admin1_name": RS_NUTS2.get(nuts3[:4], ""),
            "admin2_code": nuts3, "admin2_name": RS_NUTS3.get(nuts3, ""),
            "latitude": lat, "longitude": lon,
        })
    df = pd.DataFrame(rows)
    df["latitude"] = pd.to_numeric(df["latitude"])
    df["longitude"] = pd.to_numeric(df["longitude"])
    return _finish(df, "RS", unmatched, strict)


# --------------------------------------------------------------------------- entry point

LOADERS = {"PT": load_pt, "LU": load_lu, "RS": load_rs}


def load(country: str, path_or_dir, strict: bool = True) -> pd.DataFrame:
    cc = country.upper()
    if cc not in LOADERS:
        raise ValueError(f"no places loader for {country!r} (have {sorted(LOADERS)})")
    return LOADERS[cc](path_or_dir, strict=strict)
