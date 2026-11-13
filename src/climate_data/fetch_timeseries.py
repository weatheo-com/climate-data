"""Fetch ERA5-Land point time series (one CDS request per city).

python -m climate_data.fetch_timeseries --cities places/cities/gb.csv --ranks 1-50 \
    [--workers 4] [--cache cache/timeseries] [--variables t2m,tp,wind,ssrd] \
    [--start 1950-01-02 --end 2026-01-01] [--limit N]

Writes <cache>/<CC>/<city_id>.zip and appends to <cache>/<CC>/manifest.csv:
city_id,req_lat,req_lon,grid_lat,grid_lon,status,seconds,bytes
Exit code 2 when the run stopped after MAX_CONSECUTIVE_FAILURES failed cities.
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

DATASET = "reanalysis-era5-land-timeseries"
VARIABLES = {
    "t2m": ["2m_temperature"],
    "tp": ["total_precipitation"],
    "wind": ["10m_u_component_of_wind", "10m_v_component_of_wind"],
    "ssrd": ["surface_solar_radiation_downwards"],
}
DEFAULT_VARIABLES = "t2m,tp,wind,ssrd"
RETRY_WAITS = (30, 60, 120)
MAX_CONSECUTIVE_FAILURES = 5
NEIGHBOUR_STEP = 0.1
# N, S, E, W, then the diagonals.
NEIGHBOURS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
MANIFEST_HEADER = ["city_id", "req_lat", "req_lon", "grid_lat", "grid_lon", "status", "seconds", "bytes"]
T2M_COLUMNS = ("t2m", "2m_temperature")


def _client():
    import cdsapi

    return cdsapi.Client()


class StopRun(Exception):
    """Raised inside workers once too many consecutive cities failed."""


def parse_ranks(spec: str | None) -> tuple[int, int] | None:
    if not spec:
        return None
    if "-" in spec:
        a, b = spec.split("-", 1)
        return int(a), int(b)
    return int(spec), int(spec)


def parse_variables(spec: str) -> list[str]:
    out: list[str] = []
    for key in spec.split(","):
        key = key.strip()
        if not key:
            continue
        if key not in VARIABLES:
            raise ValueError(f"unknown variable {key!r}; choose from {','.join(VARIABLES)}")
        out.extend(VARIABLES[key])
    return out


def read_cities(path: Path, ranks: tuple[int, int] | None = None, limit: int | None = None) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if ranks:
        lo, hi = ranks
        rows = [r for r in rows if lo <= int(r["rank"]) <= hi]
    rows.sort(key=lambda r: int(r["rank"]))
    if limit:
        rows = rows[:limit]
    return rows


def build_request(lat: float, lon: float, variables: list[str], start: str, end: str) -> dict:
    return {
        "variable": list(variables),
        "location": {"longitude": round(lon, 4), "latitude": round(lat, 4)},
        "date": [f"{start}/{end}"],
        "data_format": "csv",
    }


def _csv_texts(path: Path):
    """Yield the text of each CSV in the result (a zip of CSVs, or a bare CSV)."""
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if name.lower().endswith(".csv"):
                    yield zf.read(name).decode("utf-8")
    else:
        yield path.read_text(encoding="utf-8")


def zip_ok(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        with zipfile.ZipFile(path) as zf:
            return zf.testzip() is None and bool(zf.namelist())
    except (zipfile.BadZipFile, OSError):
        return False


def inspect_result(path: Path) -> tuple[float | None, float | None, bool]:
    """Return (grid_lat, grid_lon, has_t2m_values) from the downloaded result."""
    grid_lat = grid_lon = None
    t2m_seen = False
    t2m_valid = False
    for text in _csv_texts(path):
        reader = csv.DictReader(io.StringIO(text))
        cols = reader.fieldnames or []
        t2m_col = next((c for c in T2M_COLUMNS if c in cols), None)
        for i, row in enumerate(reader):
            if i == 0 and grid_lat is None and row.get("latitude") not in (None, ""):
                grid_lat = float(row["latitude"])
                grid_lon = float(row["longitude"])
            if t2m_col is None:
                break
            t2m_seen = True
            v = (row.get(t2m_col) or "").strip()
            if v and v.lower() != "nan":
                t2m_valid = True
                break
    # No temperature column requested: do not treat the cell as sea.
    return grid_lat, grid_lon, (t2m_valid or not t2m_seen)


class Fetcher:
    def __init__(
        self,
        cache: Path,
        variables: list[str],
        start: str,
        end: str,
        client_factory: Callable = _client,
        sleep: Callable[[float], None] = time.sleep,
        retry_waits=RETRY_WAITS,
        max_failures: int = MAX_CONSECUTIVE_FAILURES,
        log: Callable[[str], None] = lambda s: print(s, flush=True),
    ):
        self.cache = Path(cache)
        self.variables = variables
        self.start = start
        self.end = end
        self.client_factory = client_factory
        self.sleep = sleep
        self.retry_waits = tuple(retry_waits)
        self.max_failures = max_failures
        self.log = log
        self._local = threading.local()
        self._lock = threading.Lock()
        self.consecutive_failures = 0
        self.stopped = threading.Event()

    # -- helpers ---------------------------------------------------------
    def client(self):
        c = getattr(self._local, "client", None)
        if c is None:
            c = self._local.client = self.client_factory()
        return c

    def manifest_path(self, cc: str) -> Path:
        return self.cache / cc / "manifest.csv"

    def append_manifest(self, cc: str, row: list) -> None:
        path = self.manifest_path(cc)
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            new = not path.exists()
            with open(path, "a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if new:
                    w.writerow(MANIFEST_HEADER)
                w.writerow(row)

    def manifest_status(self, cc: str) -> dict[str, str]:
        path = self.manifest_path(cc)
        if not path.exists():
            return {}
        with open(path, newline="", encoding="utf-8") as f:
            return {r["city_id"]: r["status"] for r in csv.DictReader(f)}

    def _retrieve(self, lat: float, lon: float, part: Path) -> None:
        req = build_request(lat, lon, self.variables, self.start, self.end)
        waits = list(self.retry_waits)
        while True:
            if self.stopped.is_set():
                raise StopRun()
            try:
                if part.exists():
                    part.unlink()
                self.client().retrieve(DATASET, req, str(part))
                return
            except StopRun:
                raise
            except Exception:
                if not waits:
                    raise
                self.sleep(waits.pop(0))

    def _record_result(self, ok: bool) -> None:
        with self._lock:
            if ok:
                self.consecutive_failures = 0
            else:
                self.consecutive_failures += 1
                if self.consecutive_failures >= self.max_failures:
                    self.stopped.set()

    # -- one city --------------------------------------------------------
    def fetch_city(self, city: dict, done_no_land: set[str] | None = None) -> str:
        if self.stopped.is_set():
            return "stopped"
        cc = city["country"].upper()
        cid = str(city["city_id"])
        out = self.cache / cc / f"{cid}.zip"
        if zip_ok(out) or (done_no_land and cid in done_no_land):
            return "skipped"
        out.parent.mkdir(parents=True, exist_ok=True)
        part = out.with_name(out.name + ".part")
        lat, lon = float(city["latitude"]), float(city["longitude"])
        t0 = time.monotonic()
        candidates = [(lat, lon)] + [
            (round(lat + dy * NEIGHBOUR_STEP, 4), round(lon + dx * NEIGHBOUR_STEP, 4)) for dy, dx in NEIGHBOURS
        ]
        status = "no_land"
        grid_lat = grid_lon = None
        size = 0
        try:
            for i, (qlat, qlon) in enumerate(candidates):
                self._retrieve(qlat, qlon, part)
                g_lat, g_lon, land = inspect_result(part)
                if land:
                    os.replace(part, out)
                    status = "ok" if i == 0 else "neighbour"
                    grid_lat, grid_lon, size = g_lat, g_lon, out.stat().st_size
                    break
            if part.exists():
                part.unlink()
        except StopRun:
            if part.exists():
                part.unlink()
            return "stopped"
        except Exception as e:  # all retries failed
            if part.exists():
                part.unlink()
            secs = time.monotonic() - t0
            self.append_manifest(cc, [cid, lat, lon, "", "", "failed", f"{secs:.1f}", 0])
            self.log(f"{city.get('name', cid)}: FAILED after {secs:.0f}s ({type(e).__name__}: {e})")
            self._record_result(False)
            return "failed"
        secs = time.monotonic() - t0
        self.append_manifest(
            cc,
            [cid, lat, lon, "" if grid_lat is None else grid_lat, "" if grid_lon is None else grid_lon,
             status, f"{secs:.1f}", size],
        )
        self.log(f"{city.get('name', cid)}: {status} {secs:.0f}s {size / 1e6:.2f} MB")
        self._record_result(True)
        return status

    # -- whole run -------------------------------------------------------
    def run(self, cities: list[dict], workers: int = 4) -> int:
        no_land: set[str] = set()
        for cc in {c["country"].upper() for c in cities}:
            no_land |= {k for k, v in self.manifest_status(cc).items() if v == "no_land"}
        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            results = list(ex.map(lambda c: self.fetch_city(c, no_land), cities))
        if self.stopped.is_set():
            self.log(f"stopped after {self.max_failures} consecutive failures; lower --workers and rerun")
            return 2
        n_fail = results.count("failed")
        self.log(f"done: {len(results)} cities, {results.count('skipped')} skipped, {n_fail} failed")
        return 0


def main(argv: list[str] | None = None, client_factory: Callable = _client) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cities", required=True, type=Path)
    ap.add_argument("--ranks", default=None, help="e.g. 1-50")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--cache", type=Path, default=Path("cache/timeseries"))
    ap.add_argument("--variables", default=DEFAULT_VARIABLES)
    ap.add_argument("--start", default="1950-01-02")
    ap.add_argument("--end", default="2026-01-01")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)
    cities = read_cities(a.cities, parse_ranks(a.ranks), a.limit)
    f = Fetcher(a.cache, parse_variables(a.variables), a.start, a.end, client_factory=client_factory)
    return f.run(cities, a.workers)


if __name__ == "__main__":
    sys.exit(main())
