"""Climate shift table (dataset B): 1961-1990 vs 1991-2020 per municipality and month."""
from __future__ import annotations

import numpy as np
import pandas as pd

OLD, NEW = "1961_1990", "1991_2020"
PLACE_COLS = ["country", "code", "name", "admin1_code", "admin1_name", "admin2_code", "admin2_name"]
# variable -> (column prefix, unit suffix, annual aggregation, shift kind)
VARS = {
    "tmean_c": ("tmean", "_c", "mean", "diff"),
    "precip_mm": ("precip", "_mm", "sum", "pct"),
    "tmax_c": ("tmax", "_c", "mean", "diff"),
    "tmin_c": ("tmin", "_c", "mean", "diff"),
    "frost_days": ("frost_days", "", "sum", "diff"),
    "summer_days": ("summer_days", "", "sum", "diff"),
}
REQUIRED = ["tmean_c", "precip_mm"]


def _with_annual(df: pd.DataFrame, keys: list[str], vars_: list[str]) -> pd.DataFrame:
    df = df.copy()
    df["month"] = df["month"].astype(int)
    bad = df.groupby(keys)["month"].apply(lambda s: sorted(s.tolist()) != list(range(1, 13)))
    if bad.any():
        raise ValueError(f"places without exactly months 1-12: {list(bad[bad].index[:3])}")
    agg = {v: VARS[v][2] for v in vars_}
    annual = df.groupby(keys, as_index=False).agg(agg)
    annual["month"] = "annual"
    df["month"] = df["month"].astype(str)
    return pd.concat([df[keys + ["month"] + vars_], annual[keys + ["month"] + vars_]], ignore_index=True)


def compute_shift(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    for v in REQUIRED:
        if v not in old.columns or v not in new.columns:
            raise ValueError(f"missing column {v}")
    vars_ = [v for v in VARS if v in old.columns and v in new.columns]
    keys = ["country", "code"] if "country" in old.columns and "country" in new.columns else ["code"]

    o = _with_annual(old, keys, vars_)
    n = _with_annual(new, keys, vars_)
    m = n.merge(o, on=keys + ["month"], how="inner", suffixes=("_new", "_old"), validate="one_to_one")
    if len(m) != len(n) or len(m) != len(o):
        raise ValueError("old and new tables cover different places")

    out = m[keys + ["month"]].copy()
    for v in vars_:
        prefix, unit, _, kind = VARS[v]
        ov = m[f"{v}_old"].astype(float).round(1)
        nv = m[f"{v}_new"].astype(float).round(1)
        out[f"{prefix}_{OLD}{unit}"] = ov
        out[f"{prefix}_{NEW}{unit}"] = nv
        if kind == "pct":
            with np.errstate(divide="ignore", invalid="ignore"):
                pct = (nv - ov) / ov * 100.0
            out[f"{prefix}_shift_pct"] = pct.where(ov != 0).round(1)
        else:
            out[f"{prefix}_shift{unit}"] = (nv - ov).round(1)

    # place attributes and url from the new table (fallback old)
    attrs = [c for c in PLACE_COLS + ["weatheo_url"] if c not in keys]
    src = new if all(c in new.columns for c in attrs if c in old.columns) else old
    have = [c for c in attrs if c in src.columns]
    if have:
        info = src[keys + have].drop_duplicates(subset=keys)
        out = out.merge(info, on=keys, how="left")
    order = [c for c in PLACE_COLS if c in out.columns] + ["month"]
    value_cols = [c for c in out.columns if c not in order and c != "weatheo_url"]
    cols = order + value_cols + (["weatheo_url"] if "weatheo_url" in out.columns else [])
    month_order = {str(i): i for i in range(1, 13)} | {"annual": 13}
    out = out.assign(_m=out["month"].map(month_order)).sort_values(keys + ["_m"]).drop(columns="_m")
    return out[cols].reset_index(drop=True)
