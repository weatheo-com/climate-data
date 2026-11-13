"""Download Copernicus CDS data (ERA5-Land / ERA5) as NetCDF, one request per year chunk.

Credentials come only from ~/.cdsapirc or the CDSAPI_URL / CDSAPI_KEY environment
variables (the cdsapi default lookup); nothing is read from this repository.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path

# Datasets whose form accepts data_format / download_format.
_FORMAT_DATASETS = {
    "reanalysis-era5-land-monthly-means",
    "reanalysis-era5-single-levels-monthly-means",
}


def _client():
    import cdsapi

    return cdsapi.Client()


def file_name(dataset: str, request: dict, bbox, y0: int, y1: int) -> str:
    key = json.dumps(request, sort_keys=True) + json.dumps(list(bbox))
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]
    return f"{dataset}_{digest}_{y0}-{y1}.nc"


def year_chunks(years, chunk: int = 10) -> list[list[int]]:
    ys = sorted(set(int(y) for y in years))
    if chunk < 1:
        raise ValueError("chunk must be >= 1")
    return [ys[i : i + chunk] for i in range(0, len(ys), chunk)]


def build_request(dataset: str, request: dict, bbox, years: list[int]) -> dict:
    n, w, s, e = bbox
    req = dict(request)
    req["year"] = [str(y) for y in years]
    req["area"] = [n, w, s, e]
    if dataset in _FORMAT_DATASETS:
        req.setdefault("data_format", "netcdf")
        req.setdefault("download_format", "unarchived")
    return req


def _merge_members(zf: zipfile.ZipFile, members: list[str], out: Path) -> None:
    """Merge several NetCDF members of a CDS zip (same grid and times) into one file."""
    import tempfile

    import xarray as xr

    with tempfile.TemporaryDirectory(dir=out.parent) as td:
        paths = []
        for i, m in enumerate(members):
            p = Path(td) / f"{i}.nc"
            with zf.open(m) as src, open(p, "wb") as dst:
                shutil.copyfileobj(src, dst)
            paths.append(p)
        dss = [xr.open_dataset(p) for p in paths]
        # Monthly means: accumulated variables are stamped 06:00, instantaneous 00:00.
        # Snap every time axis to the first of its month so the members align.
        for i, d in enumerate(dss):
            for tname in ("valid_time", "time"):
                if tname in d.coords:
                    d = d.assign_coords({tname: d[tname].values.astype("datetime64[M]").astype("datetime64[ns]")})
            dss[i] = d
        try:
            merged = xr.merge(dss, compat="override", join="exact", combine_attrs="drop_conflicts").load()
        finally:
            for d in dss:
                d.close()
        merged.to_netcdf(out)


def _extract_nc(part: Path, target: Path) -> None:
    """If `part` is a zip, extract its single .nc to `target`; else rename."""
    if zipfile.is_zipfile(part):
        with zipfile.ZipFile(part) as zf:
            members = [m for m in zf.namelist() if m.endswith(".nc")]
            if not members:
                raise RuntimeError(f"CDS zip {part.name} holds no .nc file: {zf.namelist()}")
            tmp = target.with_name(target.name + ".unzip")
            if len(members) > 1:
                # ERA5 single levels splits instantaneous (t2m, stepType avgua) and
                # accumulated (tp, stepType avgad) variables into separate files.
                _merge_members(zf, members, tmp)
                os.replace(tmp, target)
                part.unlink()
                return
            with zf.open(members[0]) as src, open(tmp, "wb") as dst:
                shutil.copyfileobj(src, dst)
        os.replace(tmp, target)
        part.unlink()
    else:
        os.replace(part, target)


def fetch(dataset: str, request: dict, bbox, years: list[int], cache_dir: Path, chunk: int = 10) -> list[Path]:
    """Retrieve `dataset` for `years` over bbox (N, W, S, E) into cache_dir.

    One CDS request per chunk of `chunk` years. Existing non-empty files are skipped.
    Returns the NetCDF paths in year order.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    client = None
    out: list[Path] = []
    for ys in year_chunks(years, chunk):
        target = cache_dir / file_name(dataset, request, bbox, ys[0], ys[-1])
        out.append(target)
        if target.exists() and target.stat().st_size > 0:
            continue
        if client is None:
            client = _client()
        part = target.with_name(target.name + ".part")
        if part.exists():
            part.unlink()
        client.retrieve(dataset, build_request(dataset, request, bbox, ys), str(part))
        if not part.exists() or part.stat().st_size == 0:
            raise RuntimeError(f"CDS returned no data for {dataset} {ys[0]}-{ys[-1]}")
        _extract_nc(part, target)
    return out
