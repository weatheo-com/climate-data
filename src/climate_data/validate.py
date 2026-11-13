"""Validate a built country dataset against its datapackage.json.

python -m climate_data.validate data/LU/datapackage.json

Checks: CSV columns and types against each resource's table schema, 12 months per place in the
normals table and 13 rows (1..12 + annual) per place in the shift table, unique (code, month),
plausible value ranges, coordinates inside the country's boxes, weatheo_url empty or on
https://weatheo.com/, attribution text in the datapackage. Exit 1 with a list of problems.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from climate_data import countries
from climate_data.datapackage import ATTRIBUTION

MAX_LISTED = 10  # offending rows listed per check
INT_RE = re.compile(r"^[+-]?\d+$")
URL_PREFIX = "https://weatheo.com/"
MONTHS_A = [str(m) for m in range(1, 13)]
MONTHS_B = MONTHS_A + ["annual"]

# (column regex, low, high, low for the annual row, high for the annual row)
RANGES = [
    (re.compile(r"^tmean_(1961_1990_|1991_2020_)?c$"), -30.0, 35.0, -30.0, 35.0),
    (re.compile(r"^(tmin|tmax)_(1961_1990_|1991_2020_)?c$"), -45.0, 50.0, -45.0, 50.0),
    (re.compile(r"^precip_(1961_1990_|1991_2020_)?mm$"), 0.0, 1500.0, 0.0, 12 * 1500.0),
    (re.compile(r"^(frost|summer)_days(_1961_1990|_1991_2020)?$"), 0.0, 31.0, 0.0, 366.0),
]


def _rows(mask: pd.Series, df: pd.DataFrame, cols: list[str]) -> str:
    bad = df.loc[mask, [c for c in cols if c in df.columns]].head(MAX_LISTED)
    items = ["(" + ", ".join(f"{c}={v}" for c, v in r.items()) + ")" for r in bad.to_dict("records")]
    more = int(mask.sum()) - len(items)
    return "; ".join(items) + (f" and {more} more" if more > 0 else "")


def check_package(pkg: dict) -> list[str]:
    probs = []
    if ATTRIBUTION not in json.dumps(pkg, ensure_ascii=False):
        probs.append("datapackage: Copernicus attribution text missing")
    lic = pkg.get("licenses") or []
    if not any(l.get("name") == "CC-BY-4.0" for l in lic):
        probs.append("datapackage: CC-BY-4.0 license missing")
    if not pkg.get("resources"):
        probs.append("datapackage: no resources")
    return probs


def check_types(df: pd.DataFrame, fields: list[dict], missing: list[str], res: str) -> list[str]:
    probs = []
    for f in fields:
        col, typ = f["name"], f.get("type", "string")
        if col not in df.columns:
            continue
        s = df[col]
        present = ~s.isin(missing)
        if typ == "integer":
            bad = present & ~s.str.match(INT_RE)
        elif typ == "number":
            num = pd.to_numeric(s.where(present), errors="coerce")
            bad = present & num.isna()
        elif typ == "boolean":
            bad = present & ~s.str.lower().isin(["true", "false"])
        else:
            continue
        if bad.any():
            probs.append(f"{res}: column {col} not {typ}: " + _rows(bad, df, ["code", "month", col]))
    return probs


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(df[col].replace("", np.nan), errors="coerce")


def check_table(df: pd.DataFrame, kind: str, cc: str | None, res: str) -> list[str]:
    probs = []
    if "code" in df.columns and "month" in df.columns:
        dup = df.duplicated(["code", "month"], keep=False)
        if dup.any():
            probs.append(f"{res}: duplicate (code, month): " + _rows(dup, df, ["code", "month"]))
        want = MONTHS_A if kind == "normals" else MONTHS_B
        bad_month = ~df["month"].isin(want)
        if bad_month.any():
            probs.append(f"{res}: month outside {want[0]}..{want[-1]}: " + _rows(bad_month, df, ["code", "month"]))
        per = df.groupby("code")["month"].agg(lambda m: sorted(set(m)) == sorted(want) and len(m) == len(want))
        wrong = per[~per].index.tolist()
        if wrong:
            n = len(want)
            probs.append(f"{res}: {len(wrong)} places without exactly {n} rows (one per month"
                         f"{' + annual' if kind == 'shift' else ''}): " + ", ".join(map(str, wrong[:MAX_LISTED])))
    annual = df["month"].eq("annual") if "month" in df.columns else pd.Series(False, index=df.index)
    for col in df.columns:
        for rx, lo, hi, alo, ahi in RANGES:
            if not rx.match(col):
                continue
            v = _num(df, col)
            low = np.where(annual, alo, lo)
            high = np.where(annual, ahi, hi)
            bad = v.notna() & ((v < low) | (v > high))
            if bad.any():
                probs.append(f"{res}: {col} outside {lo}..{hi}: " + _rows(bad, df, ["code", "month", col]))
    if "weatheo_url" in df.columns:
        u = df["weatheo_url"]
        bad = ~(u.eq("") | u.str.startswith(URL_PREFIX))
        if bad.any():
            probs.append(f"{res}: weatheo_url neither empty nor {URL_PREFIX}...: " + _rows(bad, df, ["code", "weatheo_url"]))
    if cc and {"latitude", "longitude"} <= set(df.columns):
        try:
            boxes = countries.get(cc).boxes
        except (KeyError, ValueError):
            boxes = None
            probs.append(f"{res}: unknown country {cc}, coordinates not checked")
        if boxes:
            lat, lon = _num(df, "latitude"), _num(df, "longitude")
            inside = np.zeros(len(df), dtype=bool)
            for b in boxes:
                inside |= np.asarray(b.contains(lat, lon).fillna(False), dtype=bool)
            bad = pd.Series(~inside, index=df.index)
            if bad.any():
                probs.append(f"{res}: coordinates outside the {cc} boxes: "
                             + _rows(bad, df, ["code", "latitude", "longitude"]))
    if cc and "country" in df.columns:
        bad = df["country"].ne(cc)
        if bad.any():
            probs.append(f"{res}: country is not {cc}: " + _rows(bad, df, ["code", "country"]))
    return probs


def _country(pkg: dict, df: pd.DataFrame) -> str | None:
    if "country" in df.columns and df["country"].nunique() == 1:
        return str(df["country"].iloc[0])
    sp = pkg.get("spatial")
    return sp if isinstance(sp, str) and len(sp) == 2 else None


def validate(path: str | Path) -> list[str]:
    path = Path(path)
    try:
        pkg = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"{path}: cannot read datapackage: {e}"]
    probs = check_package(pkg)
    base = path.parent
    for r in pkg.get("resources", []):
        name, rel = r.get("name", "?"), r.get("path", "")
        if r.get("format") != "csv" and not str(rel).endswith(".csv"):
            if rel and not (base / rel).exists():
                probs.append(f"{name}: file {rel} missing")
            continue
        f = base / rel
        if not f.exists():
            probs.append(f"{name}: file {rel} missing")
            continue
        sch = r.get("schema") or {}
        fields = sch.get("fields") or []
        missing = sch.get("missingValues", [""])
        try:
            df = pd.read_csv(f, dtype=str, keep_default_na=False, encoding="utf-8")
        except (UnicodeDecodeError, pd.errors.ParserError) as e:
            probs.append(f"{name}: cannot parse {rel}: {e}")
            continue
        want = [x["name"] for x in fields]
        if list(df.columns) != want:
            miss = [c for c in want if c not in df.columns]
            extra = [c for c in df.columns if c not in want]
            probs.append(f"{name}: columns differ from schema (missing {miss}, extra {extra}"
                         f"{', order differs' if not miss and not extra else ''})")
        if df.empty:
            probs.append(f"{name}: no rows")
            continue
        probs += check_types(df, fields, missing, name)
        kind = "normals" if "normals" in name else "shift" if "shift" in name else ""
        if kind:
            probs += check_table(df, kind, _country(pkg, df), name)
        pq = f.with_suffix(".parquet")
        if pq.exists():
            try:
                p = pd.read_parquet(pq)
                if len(p) != len(df) or list(p.columns) != list(df.columns):
                    probs.append(f"{name}: parquet {pq.name} differs from CSV ({len(p)} vs {len(df)} rows)")
            except Exception as e:  # noqa: BLE001 - report any unreadable parquet
                probs.append(f"{name}: cannot read {pq.name}: {e}")
    return probs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m climate_data.validate", description=__doc__.splitlines()[0])
    ap.add_argument("datapackage", type=Path)
    args = ap.parse_args(argv)
    probs = validate(args.datapackage)
    if probs:
        print(f"{args.datapackage}: {len(probs)} problem(s)")
        for p in probs:
            print(" - " + p)
        return 1
    print(f"{args.datapackage}: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
