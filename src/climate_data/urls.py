"""Join weatheo.com city page URLs to the places table.

FR rows match by INSEE code first. Everything else matches by normalised
name (accents stripped, casefolded, hyphens/apostrophes unified) when the
URL's point lies within MAX_KM of the place; the closest wins. Ambiguous
cases (two candidate pages within MAX_KM, or one page claimed by two places)
are left unmatched. Unmatched places get weatheo_url = ''.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

BASE = "https://weatheo.com"
LANG = {"FR": "fr", "LU": "fr", "PT": "pt", "RS": "en", "DE": "de", "GB": "en"}
MAX_KM = 10.0
URLS_DIR = Path(__file__).resolve().parents[2] / "places" / "urls"


def _fix_mojibake(s: str) -> str:
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def norm_name(s) -> str:
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    s = _fix_mojibake(str(s))
    s = s.replace("đ", "d").replace("Đ", "D").replace("ł", "l").replace("Ł", "L")
    s = s.replace("œ", "oe").replace("Œ", "OE").replace("æ", "ae").replace("Æ", "AE")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    s = re.sub(r"[\-‐‑–—'’`´_]", " ", s)
    s = re.sub(r"[^0-9a-z]+", " ", s)
    return " ".join(s.split())


def _haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = (np.sin((lat2 - lat1) / 2) ** 2
         + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2)
    return 6371.0088 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def _url(lang: str, path: str) -> str:
    path = str(path)
    if not path.startswith("/"):
        path = "/" + path
    return f"{BASE}/{lang}{path}"


def join_urls(places: pd.DataFrame, urls: pd.DataFrame, country: str,
              verbose: bool = True) -> pd.DataFrame:
    country = country.upper()
    lang = LANG.get(country, "en")
    out = places.copy()
    out["weatheo_url"] = ""
    u = urls.copy()
    if "country" in u.columns:
        u = u[u["country"].astype(str).str.upper() == country]
    u = u[u["path"].notna() & (u["path"].astype(str) != "")].reset_index(drop=True)
    u["code"] = u.get("code", pd.Series("", index=u.index)).fillna("").astype(str).str.strip()
    u["_n"] = u["name"].map(norm_name) if "name" in u.columns else ""
    u["_lat"] = pd.to_numeric(u.get("latitude"), errors="coerce")
    u["_lon"] = pd.to_numeric(u.get("longitude"), errors="coerce")

    used: set[int] = set()
    n_code = 0
    # 1) FR: exact INSEE code
    if country == "FR":
        codes = u[u["code"] != ""]
        dup = codes["code"].duplicated(keep=False)
        by_code = {c: i for i, c in codes.loc[~dup, "code"].items()}
        for idx, code in out["code"].astype(str).items():
            i = by_code.get(code)
            if i is not None:
                out.at[idx, "weatheo_url"] = _url(lang, u.at[i, "path"])
                used.add(i)
                n_code += 1

    # 2) normalised name within MAX_KM
    pool = u[~u.index.isin(used) & u["_lat"].notna() & u["_lon"].notna() & (u["_n"] != "")]
    groups = {k: g for k, g in pool.groupby("_n")}
    claims: dict[int, list[tuple[int, float]]] = {}
    for idx, row in out[out["weatheo_url"] == ""].iterrows():
        g = groups.get(norm_name(row["name"]))
        if g is None:
            continue
        d = _haversine_km(float(row["latitude"]), float(row["longitude"]),
                          g["_lat"].to_numpy(float), g["_lon"].to_numpy(float))
        near = np.flatnonzero(d < MAX_KM)
        if len(near) != 1:  # none, or ambiguous duplicates nearby
            continue
        i = int(g.index[near[0]])
        claims.setdefault(i, []).append((idx, float(d[near[0]])))
    n_name = 0
    for i, cl in claims.items():
        if len(cl) != 1:  # one page claimed by several places: ambiguous
            continue
        out.at[cl[0][0], "weatheo_url"] = _url(lang, u.at[i, "path"])
        n_name += 1

    if verbose:
        print(f"[urls] {country}: matched {n_code + n_name}/{len(out)} "
              f"(code {n_code}, name {n_name}); url rows {len(u)}")
    out.attrs["url_matches"] = {"code": n_code, "name": n_name, "total": len(out)}
    return out


def load_urls(country: str, path: str | Path | None = None) -> pd.DataFrame:
    p = Path(path) if path else URLS_DIR / f"{country.upper()}.csv"
    return pd.read_csv(p, dtype=str, keep_default_na=False)
