import csv
import zipfile
from pathlib import Path

from climate_data import fetch_timeseries as ft

HEADER = "country,city_id,name,ascii_name,admin1_code,admin1_name,latitude,longitude,population,timezone,rank\n"


def write_cities(path: Path, n: int = 3) -> Path:
    lines = [HEADER]
    for i in range(1, n + 1):
        lines.append(f"GB,{100 + i},City{i},City{i},ENG,England,51.{i},-0.{i},{1000 * i},Europe/London,{i}\n")
    path.write_text("".join(lines))
    return path


def make_zip(path: str, lat: float, lon: float, t2m: str = "280.5") -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(
            "reanalysis-era5-land-timeseries-a.csv",
            "valid_time,t2m,latitude,longitude\n"
            f"1950-01-02 00:00:00,{t2m},{lat},{lon}\n1950-01-02 01:00:00,{t2m},{lat},{lon}\n",
        )
        zf.writestr("reanalysis-era5-land-timeseries-b.csv",
                    f"valid_time,tp,latitude,longitude\n1950-01-02 00:00:00,0.0,{lat},{lon}\n")


class FakeClient:
    def __init__(self, calls, sea=lambda lat, lon: False, fail=0):
        self.calls = calls
        self.sea = sea
        self.fail = fail  # number of calls to fail (shared list holds count)

    def retrieve(self, dataset, req, path):
        self.calls.append((dataset, req))
        if self.fail and len(self.calls) <= self.fail:
            raise RuntimeError("boom")
        lat, lon = req["location"]["latitude"], req["location"]["longitude"]
        make_zip(path, round(lat, 1), round(lon, 1), "" if self.sea(lat, lon) else "281.0")


def fetcher(tmp_path, factory, **kw):
    kw.setdefault("sleep", lambda s: None)
    return ft.Fetcher(tmp_path / "cache", ft.parse_variables("t2m,tp,wind,ssrd"), "1950-01-02", "2026-01-01",
                      client_factory=factory, log=lambda s: None, **kw)


def manifest(tmp_path):
    with open(tmp_path / "cache" / "GB" / "manifest.csv", newline="") as f:
        return list(csv.DictReader(f))


def test_request_and_manifest_line(tmp_path):
    calls = []
    cities = ft.read_cities(write_cities(tmp_path / "gb.csv"), ft.parse_ranks("1-2"))
    assert [c["city_id"] for c in cities] == ["101", "102"]
    assert fetcher(tmp_path, lambda: FakeClient(calls)).run(cities, workers=1) == 0
    ds, req = calls[0]
    assert ds == "reanalysis-era5-land-timeseries"
    assert req["variable"] == ["2m_temperature", "total_precipitation", "10m_u_component_of_wind",
                               "10m_v_component_of_wind", "surface_solar_radiation_downwards"]
    assert req["date"] == ["1950-01-02/2026-01-01"] and req["data_format"] == "csv"
    assert req["location"] == {"longitude": -0.1, "latitude": 51.1}
    rows = manifest(tmp_path)
    assert list(rows[0].keys()) == ft.MANIFEST_HEADER
    assert rows[0]["city_id"] == "101" and rows[0]["status"] == "ok"
    assert float(rows[0]["grid_lat"]) == 51.1 and int(rows[0]["bytes"]) > 0
    assert ft.zip_ok(tmp_path / "cache" / "GB" / "101.zip")
    assert not list((tmp_path / "cache" / "GB").glob("*.part"))


def test_resume_skips_existing(tmp_path):
    calls = []
    cities = ft.read_cities(write_cities(tmp_path / "gb.csv"))
    f = fetcher(tmp_path, lambda: FakeClient(calls))
    f.run(cities, workers=2)
    assert len(calls) == 3
    # a corrupt zip is refetched, good ones skipped
    (tmp_path / "cache" / "GB" / "102.zip").write_bytes(b"garbage")
    calls.clear()
    assert fetcher(tmp_path, lambda: FakeClient(calls)).run(cities, workers=2) == 0
    assert len(calls) == 1 and calls[0][1]["location"]["latitude"] == 51.2


def test_neighbour_retry(tmp_path):
    calls = []
    # the city cell and the north neighbour are sea; the south one is land
    sea = lambda lat, lon: lat >= 51.1
    cities = ft.read_cities(write_cities(tmp_path / "gb.csv", 1))
    fetcher(tmp_path, lambda: FakeClient(calls, sea=sea)).run(cities, workers=1)
    assert [c[1]["location"]["latitude"] for c in calls] == [51.1, 51.2, 51.0]
    row = manifest(tmp_path)[0]
    assert row["status"] == "neighbour" and float(row["grid_lat"]) == 51.0
    assert row["req_lat"] == "51.1"


def test_no_land(tmp_path):
    calls = []
    cities = ft.read_cities(write_cities(tmp_path / "gb.csv", 1))
    fetcher(tmp_path, lambda: FakeClient(calls, sea=lambda a, b: True)).run(cities, workers=1)
    assert len(calls) == 9
    assert manifest(tmp_path)[0]["status"] == "no_land"
    assert not (tmp_path / "cache" / "GB" / "101.zip").exists()
    calls.clear()  # rerun does not ask again
    fetcher(tmp_path, lambda: FakeClient(calls, sea=lambda a, b: True)).run(cities, workers=1)
    assert calls == []


def test_retry_then_success(tmp_path):
    calls, waits = [], []
    cities = ft.read_cities(write_cities(tmp_path / "gb.csv", 1))
    f = fetcher(tmp_path, lambda: FakeClient(calls, fail=2), sleep=waits.append)
    assert f.run(cities, workers=1) == 0
    assert waits == [30, 60] and manifest(tmp_path)[0]["status"] == "ok"


def test_stop_after_five_failures(tmp_path):
    calls, waits = [], []
    cities = ft.read_cities(write_cities(tmp_path / "gb.csv", 8))
    f = fetcher(tmp_path, lambda: FakeClient(calls, fail=10**6), sleep=waits.append)
    assert f.run(cities, workers=1) == 2
    assert len(calls) == 5 * 4  # 1 try + 3 retries per city, 5 cities
    assert waits[:3] == [30, 60, 120]
    rows = manifest(tmp_path)
    assert len(rows) == 5 and all(r["status"] == "failed" for r in rows)


def test_main_cli(tmp_path):
    calls = []
    path = write_cities(tmp_path / "gb.csv", 4)
    rc = ft.main(["--cities", str(path), "--ranks", "2-4", "--limit", "2", "--cache", str(tmp_path / "cache"),
                  "--variables", "t2m", "--workers", "1"], client_factory=lambda: FakeClient(calls))
    assert rc == 0 and len(calls) == 2
    assert calls[0][1]["variable"] == ["2m_temperature"]
