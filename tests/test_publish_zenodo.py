"""publish_zenodo --new-version: call order with a fake HTTP session, no network."""
import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("publish_zenodo", ROOT / "scripts" / "publish_zenodo.py")
zenodo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(zenodo)

API = zenodo.SANDBOX
DRAFT = f"{API}/deposit/depositions/999"
BUCKET = f"{API}/files/bucket-999"


class Resp:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeSession:
    def __init__(self):
        self.calls, self.headers = [], {}

    def request(self, method, url, **kw):
        body = kw.get("json")
        if "data" in kw:
            body = kw["data"].read()
        self.calls.append((method, url, body))
        if url.endswith("/actions/newversion"):
            return Resp({"id": 123, "links": {"latest_draft": DRAFT}}, 201)
        if method == "GET" and url == DRAFT:
            return Resp({
                "id": 999,
                "links": {"self": DRAFT, "bucket": BUCKET, "html": "https://sandbox.zenodo.org/deposit/999",
                          "publish": f"{DRAFT}/actions/publish"},
                "metadata": {"prereserve_doi": {"doi": "10.5072/zenodo.999"}},
                "files": [
                    {"id": "f1", "filename": "de_a.csv", "links": {"self": f"{DRAFT}/files/f1"}},
                    {"id": "f2", "filename": "old.csv", "links": {"self": f"{DRAFT}/files/f2"}},
                ],
            })
        if method == "PUT" and url == DRAFT:
            return Resp({"id": 999, "links": {"self": DRAFT, "html": "https://sandbox.zenodo.org/deposit/999"},
                         "metadata": dict(body["metadata"], prereserve_doi={"doi": "10.5072/zenodo.999"})})
        if url.endswith("/actions/publish"):
            return Resp({"id": 999, "links": {"html": "https://sandbox.zenodo.org/records/999"},
                         "doi": "10.5072/zenodo.999"}, 202)
        return Resp({}, 204 if method == "DELETE" else 201)


@pytest.fixture
def setup(tmp_path):
    meta = tmp_path / "m.json"
    meta.write_text(json.dumps({"title": "T", "description": "D", "tags": ["a"], "version": "1.0.0",
                                "publication_date": "2020-01-01"}))
    a, b = tmp_path / "de_a.csv", tmp_path / "gb_b.csv"
    a.write_text("x\n1\n")
    b.write_text("y\n2\n")
    return meta, a, b


def _run(setup, *extra):
    meta, a, b = setup
    s = FakeSession()
    rc = zenodo.main(["--meta", str(meta), "--files", str(a), str(b), "--new-version", "123",
                      "--version", "1.1.0", *extra], session=s, env={"ZENODO_SANDBOX_TOKEN": "tok"})
    assert rc == 0
    return s


def test_new_version_order_no_publish(setup, capsys):
    s = _run(setup)
    order = [(m, u) for m, u, _ in s.calls]
    assert order == [
        ("POST", f"{API}/deposit/depositions/123/actions/newversion"),
        ("GET", DRAFT),
        ("DELETE", f"{DRAFT}/files/f1"),
        ("PUT", f"{BUCKET}/de_a.csv"),
        ("PUT", f"{BUCKET}/gb_b.csv"),
        ("PUT", DRAFT),
    ]
    assert s.calls[3][2] == b"x\n1\n"
    md = s.calls[-1][2]["metadata"]
    assert md["version"] == "1.1.0"
    assert md["publication_date"] == date.today().isoformat()
    out = capsys.readouterr().out
    assert "https://sandbox.zenodo.org/deposit/999" in out
    assert "reserved DOI: 10.5072/zenodo.999" in out
    assert s.headers["Authorization"] == "Bearer tok"


def test_new_version_replace_files_and_publish(setup):
    s = _run(setup, "--replace-files", "--publish")
    order = [(m, u) for m, u, _ in s.calls]
    assert ("DELETE", f"{DRAFT}/files/f1") in order and ("DELETE", f"{DRAFT}/files/f2") in order
    assert order[-1] == ("POST", f"{DRAFT}/actions/publish")
    assert order.index(("PUT", DRAFT)) < len(order) - 1


def test_new_version_dry_run_sends_nothing(setup, capsys):
    meta, a, b = setup
    s = FakeSession()
    rc = zenodo.main(["--meta", str(meta), "--files", str(a), str(b), "--new-version", "123"],
                     session=s, env={})
    assert rc == 0 and s.calls == []
    out = capsys.readouterr().out
    assert "/deposit/depositions/123/actions/newversion" in out
    assert "actions/publish" not in out
    assert '"version": "1.0.0"' in out
