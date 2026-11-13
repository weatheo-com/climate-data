import zipfile

import cdsapi
import pytest

from climate_data import fetch_cds

DS = "reanalysis-era5-land-monthly-means"
REQ = {
    "product_type": "monthly_averaged_reanalysis",
    "variable": ["2m_temperature", "total_precipitation"],
    "month": ["01", "02"],
    "time": ["00:00"],
}
BBOX = (50.2, 5.7, 49.4, 6.6)


class FakeClient:
    calls: list = []
    mode = "nc"

    def __init__(self, *a, **k):
        pass

    def retrieve(self, dataset, request, target):
        FakeClient.calls.append((dataset, request, target))
        if FakeClient.mode == "zip":
            with zipfile.ZipFile(target, "w") as zf:
                zf.writestr("data_0.nc", b"NCDATA")
        else:
            with open(target, "wb") as f:
                f.write(b"CDF\x01" + request["year"][0].encode())


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    FakeClient.calls = []
    FakeClient.mode = "nc"
    monkeypatch.setattr(cdsapi, "Client", FakeClient)
    return FakeClient


def test_chunks_and_requests(tmp_path):
    years = list(range(1991, 2021))
    paths = fetch_cds.fetch(DS, REQ, BBOX, years, tmp_path)
    assert len(FakeClient.calls) == 3
    spans = [(c[1]["year"][0], c[1]["year"][-1], len(c[1]["year"])) for c in FakeClient.calls]
    assert spans == [("1991", "2000", 10), ("2001", "2010", 10), ("2011", "2020", 10)]
    ds, r, target = FakeClient.calls[0]
    assert ds == DS
    assert r["area"] == [50.2, 5.7, 49.4, 6.6]
    assert r["data_format"] == "netcdf" and r["download_format"] == "unarchived"
    assert r["variable"] == REQ["variable"] and r["month"] == ["01", "02"]
    assert target.endswith(".part")
    assert "year" not in REQ  # input not mutated
    assert [p.name for p in paths] == [
        fetch_cds.file_name(DS, REQ, BBOX, 1991, 2000),
        fetch_cds.file_name(DS, REQ, BBOX, 2001, 2010),
        fetch_cds.file_name(DS, REQ, BBOX, 2011, 2020),
    ]
    assert paths[0].name.startswith(DS + "_") and paths[0].name.endswith("_1991-2000.nc")
    assert all(p.exists() and p.stat().st_size > 0 for p in paths)
    assert not list(tmp_path.glob("*.part"))


def test_uneven_chunk(tmp_path):
    fetch_cds.fetch(DS, REQ, BBOX, [1961, 1962, 1963, 1964, 1965], tmp_path, chunk=2)
    assert [c[1]["year"] for c in FakeClient.calls] == [["1961", "1962"], ["1963", "1964"], ["1965"]]


def test_skip_existing(tmp_path):
    years = list(range(1991, 2011))
    fetch_cds.fetch(DS, REQ, BBOX, years, tmp_path)
    assert len(FakeClient.calls) == 2
    FakeClient.calls = []
    paths = fetch_cds.fetch(DS, REQ, BBOX, years, tmp_path)
    assert FakeClient.calls == []
    # an empty file is re-downloaded
    paths[1].write_bytes(b"")
    fetch_cds.fetch(DS, REQ, BBOX, years, tmp_path)
    assert len(FakeClient.calls) == 1 and FakeClient.calls[0][1]["year"][0] == "2001"


def test_hash_depends_on_request_and_bbox():
    a = fetch_cds.file_name(DS, REQ, BBOX, 1991, 2000)
    b = fetch_cds.file_name(DS, {**REQ, "month": ["01"]}, BBOX, 1991, 2000)
    c = fetch_cds.file_name(DS, REQ, (51, 5.7, 49.4, 6.6), 1991, 2000)
    assert len({a, b, c}) == 3


def test_zip_extracted(tmp_path):
    FakeClient.mode = "zip"
    (p,) = fetch_cds.fetch(DS, REQ, BBOX, [2020], tmp_path)
    assert p.read_bytes() == b"NCDATA"
    assert not zipfile.is_zipfile(p)
    assert sorted(x.name for x in tmp_path.iterdir()) == [p.name]


def test_no_format_keys_for_daily_dataset(tmp_path):
    fetch_cds.fetch("derived-era5-land-daily-statistics", {"variable": ["2m_temperature"]}, BBOX, [2020], tmp_path)
    r = FakeClient.calls[0][1]
    assert "data_format" not in r and "download_format" not in r


def test_zip_with_two_members_is_merged(tmp_path):
    import zipfile

    import numpy as np
    import xarray as xr

    from climate_data.fetch_cds import _extract_nc

    # Real CDS monthly means: instantaneous t2m at 00:00, accumulated tp at 06:00.
    def coords(hour):
        return {"valid_time": np.array([f"2000-01-01T{hour}", f"2000-02-01T{hour}"], dtype="datetime64[ns]"), "latitude": [50.0], "longitude": [6.0]}

    a, b = tmp_path / "a.nc", tmp_path / "b.nc"
    xr.Dataset({"t2m": (("valid_time", "latitude", "longitude"), [[[280.0]], [[281.0]]])}, coords=coords("00:00")).to_netcdf(a)
    xr.Dataset({"tp": (("valid_time", "latitude", "longitude"), [[[0.002]], [[0.003]]])}, coords=coords("06:00")).to_netcdf(b)
    part = tmp_path / "x.nc.part"
    with zipfile.ZipFile(part, "w") as zf:
        zf.write(a, "data_stream-moda_stepType-avgua.nc")
        zf.write(b, "data_stream-moda_stepType-avgad.nc")
    target = tmp_path / "x.nc"
    _extract_nc(part, target)
    ds = xr.open_dataset(target)
    assert sorted(ds.data_vars) == ["t2m", "tp"]
    assert ds.sizes["valid_time"] == 2
    assert str(ds.valid_time.values[1])[:16] == "2000-02-01T00:00"
    assert float(ds.tp.values[1, 0, 0]) == 0.003
    assert not part.exists()
    ds.close()
