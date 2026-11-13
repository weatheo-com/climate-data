"""Publisher scripts: payloads, matching and request order, with no network."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
META = ROOT / "portals" / "example" / "FR-A.json"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


udata = _load("publish_udata")
zenodo = _load("publish_zenodo")


class Resp:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status
        self.content = json.dumps(data).encode()

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeSession:
    """Records every call; answers from a list of canned responses."""

    def __init__(self, answers=()):
        self.calls, self.answers, self.headers = [], list(answers), {}

    def _next(self, method, url, **kw):
        self.calls.append((method, url, kw))
        return self.answers.pop(0) if self.answers else Resp({})

    def get(self, url, **kw):
        return self._next("GET", url, **kw)

    def put(self, url, **kw):
        return self._next("PUT", url, **kw)

    def request(self, method, url, **kw):
        return self._next(method, url, **kw)


@pytest.fixture
def meta():
    return json.loads(META.read_text(encoding="utf-8"))


def test_udata_dry_run_sends_nothing(capsys, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network used")

    monkeypatch.setattr("socket.socket.connect", boom)
    assert udata.main(["--base", "https://www.data.gouv.fr", "--meta", str(META)]) == 0
    out = capsys.readouterr().out
    assert "POST https://www.data.gouv.fr/api/1/datasets/" in out
    assert '"license": "cc-by"' in out
    assert '"filetype": "remote"' in out


def test_udata_create_plan(meta):
    reqs = udata.plan("https://dados.gov.pt/", meta, "org1", None)
    assert reqs[0]["method"] == "POST" and reqs[0]["url"] == "https://dados.gov.pt/api/1/datasets/"
    body = reqs[0]["json"]
    assert body["organization"] == "org1" and body["license"] == "cc-by" and body["frequency"] == "irregular"
    assert body["tags"] == meta["tags"] and "resources" not in body
    assert len(reqs) == 1 + len(meta["resources"])
    assert all(r["url"].endswith("/datasets/{new_dataset_id}/resources/") for r in reqs[1:])
    assert reqs[1]["json"]["url"].startswith("https://github.com/")


def test_udata_match_and_update(meta):
    existing = [
        {"id": "x", "slug": "other", "title": "Other"},
        {"id": "d1", "slug": "renamed", "title": meta["title"]},
    ]
    assert udata.find_existing(existing, meta)["id"] == "d1"
    assert udata.find_existing([{"id": "s", "slug": meta["slug"], "title": "old"}] + existing, meta)["id"] == "s"
    full = {"id": "d1", "resources": [{"id": "r1", "title": meta["resources"][0]["title"], "url": "old"}]}
    reqs = udata.plan("https://data.public.lu", meta, None, full)
    assert reqs[0]["method"] == "PUT" and reqs[0]["url"].endswith("/datasets/d1/")
    assert reqs[1]["method"] == "PUT" and reqs[1]["url"].endswith("/datasets/d1/resources/r1/")
    assert all(r["method"] == "POST" for r in reqs[2:])


def test_udata_apply_creates_with_key(meta, monkeypatch):
    monkeypatch.setenv("UDATA_API_KEY", "k")
    s = FakeSession([Resp({"data": []}), Resp({"id": "new", "page": "p"})])
    assert udata.main(["--base", "https://data.gov.rs", "--meta", str(META), "--org", "o", "--apply"], session=s) == 0
    assert s.headers["X-API-KEY"] == "k"
    assert s.calls[0][:2] == ("GET", "https://data.gov.rs/api/1/organizations/o/datasets/?page_size=100")
    assert s.calls[1][:2] == ("POST", "https://data.gov.rs/api/1/datasets/")
    assert [c[1] for c in s.calls[2:]] == ["https://data.gov.rs/api/1/datasets/new/resources/"] * len(meta["resources"])


def test_udata_apply_needs_key(monkeypatch):
    monkeypatch.delenv("UDATA_API_KEY", raising=False)
    s = FakeSession()
    assert udata.main(["--base", "https://www.data.gouv.fr", "--meta", str(META), "--apply"], session=s) == 2
    assert s.calls == []


def test_zenodo_metadata(meta):
    md = zenodo.metadata(meta)
    assert md["creators"] == [{"name": "Weatheo (by CODELIO)"}]
    assert md["license"] == "cc-by-4.0" and md["upload_type"] == "dataset"
    ids = {r["identifier"] for r in md["related_identifiers"]}
    assert ids == {"https://github.com/weatheo-com/climate-data", "https://weatheo.com/en/open-data"}
    repo = next(r for r in md["related_identifiers"] if "github.com" in r["identifier"])
    assert repo["relation"] == "isSupplementTo"
    override = dict(meta, zenodo={"related_identifiers": [{"identifier": "x", "relation": "isDerivedFrom"}]})
    assert zenodo.metadata(override)["related_identifiers"] == [{"identifier": "x", "relation": "isDerivedFrom"}]


def test_zenodo_token_choice():
    assert zenodo.token_for(False, {"ZENODO_SANDBOX_TOKEN": "s", "ZENODO_TOKEN": "p"}) == "s"
    assert zenodo.token_for(False, {"ZENODO_TOKEN": "p"}) == "p"
    assert zenodo.token_for(True, {"ZENODO_SANDBOX_TOKEN": "s"}) is None


def test_zenodo_no_token_prints(tmp_path, capsys):
    f = tmp_path / "a.csv"
    f.write_text("x\n1\n")
    s = FakeSession()
    assert zenodo.main(["--meta", str(META), "--files", str(f)], session=s, env={}) == 0
    assert s.calls == []
    out = capsys.readouterr().out
    assert "POST https://sandbox.zenodo.org/api/deposit/depositions" in out and "cc-by-4.0" in out
    assert "actions/publish" not in out


def test_zenodo_draft_then_publish(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("x\n1\n")
    created = {"id": 7, "links": {"bucket": "https://sandbox.zenodo.org/api/files/b1", "html": "h"}}
    s = FakeSession([Resp(created), Resp({}), Resp(created)])
    assert zenodo.main(["--meta", str(META), "--files", str(f)], session=s, env={"ZENODO_SANDBOX_TOKEN": "t"}) == 0
    assert s.headers["Authorization"] == "Bearer t"
    assert [c[:2] for c in s.calls] == [
        ("POST", "https://sandbox.zenodo.org/api/deposit/depositions"),
        ("PUT", "https://sandbox.zenodo.org/api/files/b1/a.csv"),
        ("PUT", "https://sandbox.zenodo.org/api/deposit/depositions/7"),
    ]
    assert s.calls[2][2]["json"]["metadata"]["license"] == "cc-by-4.0"

    s = FakeSession([Resp(created), Resp({}), Resp(created), Resp(created)])
    zenodo.main(["--meta", str(META), "--files", str(f), "--production", "--publish"], session=s,
                env={"ZENODO_TOKEN": "p"})
    assert s.calls[-1][:2] == ("POST", "https://zenodo.org/api/deposit/depositions/7/actions/publish")


PORTALS = ROOT / "portals"
REUSE = PORTALS / "data.gouv.fr" / "REUSE.json"
DS_ID = "0123456789abcdef01234567"


def test_udata_spatial_in_payload():
    fr = json.loads((PORTALS / "data.gouv.fr" / "FR-A.json").read_text(encoding="utf-8"))
    body = udata.plan("https://www.data.gouv.fr", fr, None, None)[0]["json"]
    assert body["spatial"] == {"granularity": "fr:commune", "zones": ["country-subset:fr:metro"]}
    put = udata.plan("https://www.data.gouv.fr", fr, None, {"id": "d1"})[0]
    assert put["method"] == "PUT" and put["json"]["spatial"] == body["spatial"]
    metas = [f for d in ("data.gouv.fr", "dados.gov.pt", "data.public.lu", "data.gov.rs")
             for f in (PORTALS / d).glob("??-?.json")]
    assert len(metas) == 8
    for f in metas:
        m = json.loads(f.read_text(encoding="utf-8"))
        sp = udata.dataset_payload(m, None)["spatial"]
        assert sp == {"granularity": m["spatial"]["granularity"], "zones": m["spatial"]["zones"]}, f.name


def _reuse_meta(tmp_path, **extra):
    m = json.loads(REUSE.read_text(encoding="utf-8"))
    m.update(extra)
    f = tmp_path / "REUSE.json"
    f.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return f, m


def test_udata_reuse_dry_run_sends_nothing(tmp_path, capsys, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network used")

    monkeypatch.setattr("socket.socket.connect", boom)
    assert udata.main(["--base", "https://www.data.gouv.fr", "--reuse", str(REUSE)]) == 0
    out = capsys.readouterr().out
    assert "POST https://www.data.gouv.fr/api/1/reuses/" in out
    assert '"topic": "environment_and_energy"' in out and '"type": "application"' in out

    f, _ = _reuse_meta(tmp_path, datasets=["liste-des-communes-de-france", DS_ID])
    assert udata.main(["--base", "https://www.data.gouv.fr", "--reuse", str(f)]) == 0
    out = capsys.readouterr().out
    assert "GET https://www.data.gouv.fr/api/1/datasets/liste-des-communes-de-france/" in out
    assert "{slug:liste-des-communes-de-france}" in out and DS_ID in out


def test_udata_reuse_lookup_resolves_slugs(tmp_path, capsys):
    f, m = _reuse_meta(tmp_path, datasets=["liste-des-communes-de-france", DS_ID])
    s = FakeSession([Resp({"id": "a" * 24, "slug": "liste-des-communes-de-france"}), Resp({"data": []})])
    assert udata.main(["--base", "https://www.data.gouv.fr", "--reuse", str(f), "--org", "o", "--lookup"],
                      session=s) == 0
    assert [c[:2] for c in s.calls] == [
        ("GET", "https://www.data.gouv.fr/api/1/datasets/liste-des-communes-de-france/"),
        ("GET", "https://www.data.gouv.fr/api/1/organizations/o/reuses/"),
    ]
    reqs = udata.plan_reuse("https://www.data.gouv.fr", m, "o", None, ["a" * 24, DS_ID])
    body = reqs[0]["json"]
    assert reqs[0]["method"] == "POST" and reqs[0]["url"] == "https://www.data.gouv.fr/api/1/reuses/"
    assert body["datasets"] == ["a" * 24, DS_ID] and body["organization"] == "o"
    assert {k: body[k] for k in ("title", "url", "type", "topic", "tags")} == {
        k: m[k] for k in ("title", "url", "type", "topic", "tags")}
    assert "datasets_note" not in body
    out = capsys.readouterr().out
    assert '"aaaaaaaaaaaaaaaaaaaaaaaa"' in out and "{slug:" not in out


def test_udata_reuse_apply_create_with_image(tmp_path, monkeypatch):
    monkeypatch.setenv("UDATA_API_KEY", "k")
    (tmp_path / "shot.png").write_bytes(b"png")
    f, m = _reuse_meta(tmp_path, datasets=[DS_ID], image="shot.png")
    s = FakeSession([Resp({"data": [{"id": "other", "title": "Other"}]}), Resp({"id": "r9", "page": "p"}), Resp({})])
    assert udata.main(["--base", "https://www.data.gouv.fr", "--reuse", str(f), "--org", "o", "--apply"],
                      session=s) == 0
    assert [c[:2] for c in s.calls] == [
        ("GET", "https://www.data.gouv.fr/api/1/organizations/o/reuses/"),
        ("POST", "https://www.data.gouv.fr/api/1/reuses/"),
        ("POST", "https://www.data.gouv.fr/api/1/reuses/r9/image/"),
    ]
    assert s.calls[1][2]["json"]["datasets"] == [DS_ID]
    assert s.calls[2][2]["files"]["file"][0] == "shot.png"


def test_udata_reuse_update_by_title(tmp_path, monkeypatch):
    monkeypatch.setenv("UDATA_API_KEY", "k")
    f, m = _reuse_meta(tmp_path, datasets=[DS_ID])
    s = FakeSession([Resp([{"id": "r1", "title": m["title"]}]), Resp({"id": "r1"})])
    assert udata.main(["--base", "https://www.data.gouv.fr", "--reuse", str(f), "--apply"], session=s) == 0
    assert s.calls[0][:2] == ("GET", "https://www.data.gouv.fr/api/1/me/reuses/")
    assert s.calls[1][:2] == ("PUT", "https://www.data.gouv.fr/api/1/reuses/r1/")
    assert len(s.calls) == 2


def test_udata_reuse_needs_required_fields(tmp_path):
    f, _ = _reuse_meta(tmp_path, topic="")
    assert udata.main(["--base", "https://www.data.gouv.fr", "--reuse", str(f)]) == 2


def _pkg(tmp_path, cc, name="datapackage.json"):
    d = tmp_path / "data" / cc
    d.mkdir(parents=True, exist_ok=True)
    f = d / name
    f.write_text("{}")
    return f


def test_zenodo_renames_datapackages(tmp_path):
    fr, pt = _pkg(tmp_path, "FR"), _pkg(tmp_path, "PT")
    csv = _pkg(tmp_path, "FR", "FR_x.csv")
    names = [n for _, n in zenodo.upload_names([csv, fr, pt])]
    assert names == ["FR_x.csv", "FR_datapackage.json", "PT_datapackage.json"]
    assert [n for _, n in zenodo.upload_names([csv, fr])] == ["FR_x.csv", "datapackage.json"]
    reqs = zenodo.plan(zenodo.SANDBOX, {"title": "t"}, [fr, pt], False)
    assert [r["url"] for r in reqs[1:3]] == ["{bucket}/FR_datapackage.json", "{bucket}/PT_datapackage.json"]


def test_zenodo_duplicate_names_error(tmp_path, capsys):
    a, b = _pkg(tmp_path, "FR", "x.csv"), _pkg(tmp_path, "PT", "x.csv")
    with pytest.raises(ValueError, match="x.csv"):
        zenodo.upload_names([a, b])
    s = FakeSession()
    assert zenodo.main(["--meta", str(META), "--files", str(a), str(b)], session=s, env={"ZENODO_TOKEN": "t"}) == 2
    assert s.calls == [] and "duplicate" in capsys.readouterr().err
