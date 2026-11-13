"""France places loader: one row per commune, keyed by INSEE code."""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

COLUMNS = [
    "country", "code", "name", "admin1_code", "admin1_name",
    "admin2_code", "admin2_name", "latitude", "longitude",
]


def _pad(s: pd.Series, width: int) -> pd.Series:
    """Restore leading zeros lost by spreadsheet exports (1001 -> 01001); 2A004 kept as is."""
    s = s.fillna("").astype(str).str.strip()
    numeric = s.str.fullmatch(r"\d+")
    return s.where(~numeric, s.str.zfill(width))


def _coord(df: pd.DataFrame, axis: str) -> pd.Series:
    """Commune centre if present, else town hall."""
    out = pd.Series(float("nan"), index=df.index)
    for col in (f"{axis}_centre", f"{axis}_mairie"):
        if col in df.columns:
            out = out.fillna(pd.to_numeric(df[col], errors="coerce"))
    return out


def load(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])
    out = pd.DataFrame({
        "country": "FR",
        "code": _pad(df["code_insee"], 5),
        "name": df["nom_standard"].fillna("").astype(str),
        "admin1_code": _pad(df["reg_code"], 2),
        "admin1_name": df["reg_nom"].fillna("").astype(str),
        "admin2_code": _pad(df["dep_code"], 2),
        "admin2_name": df["dep_nom"].fillna("").astype(str),
        "latitude": _coord(df, "latitude"),
        "longitude": _coord(df, "longitude"),
    })
    bad = (out["code"] == "") | out["latitude"].isna() | out["longitude"].isna()
    if bad.any():
        log.warning("places_fr: dropped %d rows with missing code or coordinates", int(bad.sum()))
    out = out[~bad].reset_index(drop=True)
    dup = out["code"][out["code"].duplicated()]
    if len(dup):
        raise ValueError(f"places_fr: duplicated INSEE codes: {sorted(dup.unique())[:10]}")
    out["latitude"] = out["latitude"].astype(float)
    out["longitude"] = out["longitude"].astype(float)
    return out[COLUMNS]
