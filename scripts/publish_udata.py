#!/usr/bin/env python3
"""Create or update a dataset or a reuse on a uData portal (API v1), dry-run by default.

Portals: https://www.data.gouv.fr, https://dados.gov.pt, https://data.public.lu,
https://data.gov.rs (all uData, API v1 under /api/1/).

    python scripts/publish_udata.py --base https://www.data.gouv.fr \
        --meta portals/example/FR-A.json [--org <org id>] [--lookup] [--apply]
    python scripts/publish_udata.py --base https://www.data.gouv.fr \
        --reuse portals/data.gouv.fr/REUSE.json [--org <org id>] [--lookup] [--apply]

Without --apply nothing is sent: the script prints every request it would make
with its JSON payload. --lookup allows read-only GETs in a dry run to decide
create vs update (and to resolve a reuse's dataset slugs to ids). With --apply
the API key is read from env UDATA_API_KEY and sent as the X-API-KEY header.

Meta file keys: slug, title, description, tags, license (uData licence id, e.g.
"cc-by"; list at /api/1/datasets/licenses/), frequency (enum from
/api/1/datasets/frequencies/, e.g. "irregular"), optional temporal_coverage
{start, end}, optional spatial {granularity, zones} (uData ids, sent as is, e.g.
{"granularity": "fr:commune", "zones": ["country-subset:fr:metro"]}; granularities
at /api/1/spatial/granularities/), resources [{title, url, format, mime?, type?,
description?}] pointing at remote files (GitHub release assets).

Reuse meta keys (--reuse): title, description, url, type (/api/1/reuses/types/),
topic (/api/1/reuses/topics/), tags, datasets (slugs or 24-hex ids; slugs are
resolved with GET /api/1/datasets/<slug>/), optional private, optional image
(file path relative to the meta file, uploaded to /api/1/reuses/<id>/image/).
The reuse is matched by title within --org (or the key owner's reuses).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

DATASET_FIELDS = ("title", "description", "tags", "license", "frequency", "temporal_coverage")
RESOURCE_FIELDS = ("title", "url", "format", "mime", "type", "description")
REUSE_FIELDS = ("title", "description", "url", "type", "topic", "tags", "private")
REUSE_REQUIRED = ("title", "description", "url", "type", "topic")
NEW_IDS = ("{new_dataset_id}", "{new_reuse_id}")
OBJECT_ID = re.compile(r"[0-9a-f]{24}")


def api(base: str) -> str:
    return base.rstrip("/") + "/api/1"


def spatial_payload(spatial: dict) -> dict:
    """uData SpatialCoverage write shape: {"granularity": "<id>", "zones": ["<zone id>", ...]}."""
    out: dict = {}
    if spatial.get("granularity"):
        out["granularity"] = spatial["granularity"]
    zones = spatial.get("zones")
    if zones:
        out["zones"] = [zones] if isinstance(zones, str) else list(zones)
    return out


def dataset_payload(meta: dict, org: str | None) -> dict:
    payload = {k: meta[k] for k in DATASET_FIELDS if k in meta}
    if meta.get("spatial"):
        payload["spatial"] = spatial_payload(meta["spatial"])
    payload.setdefault("license", "cc-by")
    payload.setdefault("frequency", "irregular")
    if org:
        payload["organization"] = org
    return payload


def resource_payload(res: dict) -> dict:
    payload = {k: res[k] for k in RESOURCE_FIELDS if k in res}
    payload.setdefault("type", "main")
    payload["filetype"] = "remote"
    return payload


def find_existing(datasets: list[dict], meta: dict) -> dict | None:
    """Match on slug first, then on title."""
    for key in ("slug", "title"):
        want = meta.get(key)
        if not want:
            continue
        for d in datasets:
            if d.get(key) == want and not d.get("deleted"):
                return d
    return None


def plan(base: str, meta: dict, org: str | None, existing: dict | None) -> list[dict]:
    """Ordered list of write requests: {method, url, json}. Pure (no network)."""
    root = api(base)
    reqs: list[dict] = []
    if existing is None:
        reqs.append({"method": "POST", "url": f"{root}/datasets/", "json": dataset_payload(meta, org)})
        ds = "{new_dataset_id}"
        old_res: list[dict] = []
    else:
        ds = existing["id"]
        reqs.append({"method": "PUT", "url": f"{root}/datasets/{ds}/", "json": dataset_payload(meta, org)})
        old_res = existing.get("resources") or []
    for res in meta.get("resources", []):
        body = resource_payload(res)
        match = next((r for r in old_res if r.get("title") == body["title"] or r.get("url") == body["url"]), None)
        if match:
            reqs.append({"method": "PUT", "url": f"{root}/datasets/{ds}/resources/{match['id']}/", "json": body})
        else:
            reqs.append({"method": "POST", "url": f"{root}/datasets/{ds}/resources/", "json": body})
    return reqs


def lookup_url(base: str, org: str | None) -> str:
    root = api(base)
    return f"{root}/organizations/{org}/datasets/?page_size=100" if org else f"{root}/me/datasets/"


def _items(body) -> list[dict]:
    return body.get("data", body) if isinstance(body, dict) else body


def fetch_existing(session, base: str, meta: dict, org: str | None) -> dict | None:
    """Read-only lookup of a matching dataset in the org (or the key owner's datasets)."""
    r = session.get(lookup_url(base, org), timeout=60)
    r.raise_for_status()
    found = find_existing(_items(r.json()), meta)
    if found is None:
        return None
    full = session.get(f"{api(base)}/datasets/{found['id']}/", timeout=60)
    full.raise_for_status()
    return full.json()


def is_object_id(ref: str) -> bool:
    return bool(OBJECT_ID.fullmatch(ref))


def reuse_payload(meta: dict, org: str | None, dataset_ids: list[str]) -> dict:
    payload = {k: meta[k] for k in REUSE_FIELDS if k in meta}
    payload["datasets"] = list(dataset_ids)
    if org:
        payload["organization"] = org
    return payload


def plan_reuse(base: str, meta: dict, org: str | None, existing: dict | None, dataset_ids: list[str],
               image: Path | None = None) -> list[dict]:
    """Write requests for a reuse (pure): POST or PUT, then the optional image upload."""
    root = api(base)
    body = reuse_payload(meta, org, dataset_ids)
    if existing is None:
        reqs = [{"method": "POST", "url": f"{root}/reuses/", "json": body}]
        rid = "{new_reuse_id}"
    else:
        rid = existing["id"]
        reqs = [{"method": "PUT", "url": f"{root}/reuses/{rid}/", "json": body}]
    if image is not None:
        reqs.append({"method": "POST", "url": f"{root}/reuses/{rid}/image/", "json": None, "file": str(image)})
    return reqs


def reuse_lookup_url(base: str, org: str | None) -> str:
    root = api(base)
    return f"{root}/organizations/{org}/reuses/" if org else f"{root}/me/reuses/"


def fetch_existing_reuse(session, base: str, meta: dict, org: str | None) -> dict | None:
    """Read-only lookup of a reuse with the same title in the org (or the key owner's reuses)."""
    r = session.get(reuse_lookup_url(base, org), timeout=60)
    r.raise_for_status()
    return find_existing(_items(r.json()), meta)


def resolve_datasets(session, base: str, refs: list[str]) -> list[str]:
    """Dataset slugs -> ids with read-only GETs; refs that already are ids are kept."""
    ids = []
    for ref in refs:
        if is_object_id(ref):
            ids.append(ref)
            continue
        r = session.get(f"{api(base)}/datasets/{ref}/", timeout=60)
        r.raise_for_status()
        ids.append(r.json()["id"])
    return ids


def print_plan(reqs: list[dict], out=None) -> None:
    out = out or sys.stdout
    for r in reqs:
        print(f"{r['method']} {r['url']}", file=out)
        if "file" in r:
            print(f"  <multipart form, field 'file': {r['file']}>", file=out)
        else:
            print(json.dumps(r["json"], ensure_ascii=False, indent=2), file=out)


def execute(session, reqs: list[dict]) -> dict:
    new_id = None
    result: dict = {}
    for r in reqs:
        url = r["url"]
        for ph in NEW_IDS:
            if ph in url:
                if not new_id:
                    raise RuntimeError("new object id unknown before a follow-up request")
                url = url.replace(ph, new_id)
        if "file" in r:
            with open(r["file"], "rb") as fh:
                resp = session.request(r["method"], url, files={"file": (Path(r["file"]).name, fh)}, timeout=120)
        else:
            resp = session.request(r["method"], url, json=r["json"], timeout=120)
        resp.raise_for_status()
        data = resp.json() if resp.content else {}
        if not result:
            result = data
            new_id = data.get("id")
        print(f"{r['method']} {url} -> {resp.status_code}")
    return result


def open_session(a, session):
    """(session, exit code): a session only with --apply or --lookup; --apply needs UDATA_API_KEY."""
    if not (a.apply or a.lookup):
        return session, 0
    key = os.environ.get("UDATA_API_KEY")
    if a.apply and not key:
        print("UDATA_API_KEY is not set", file=sys.stderr)
        return session, 2
    if session is None:
        import requests

        session = requests.Session()
    if key:
        session.headers.update({"X-API-KEY": key})
    return session, 0


def run_reuse(a, session) -> int:
    meta = json.loads(a.reuse.read_text(encoding="utf-8"))
    missing = [k for k in REUSE_REQUIRED if not meta.get(k)]
    if missing:
        print(f"reuse meta lacks: {', '.join(missing)}", file=sys.stderr)
        return 2
    refs = list(meta.get("datasets") or [])
    if not refs:
        print("# warning: no 'datasets' in the reuse meta, the reuse would link no dataset")
    image = (a.reuse.parent / meta["image"]) if meta.get("image") else None
    if image is not None and not image.is_file():
        if a.apply:
            print(f"reuse image not found: {image}", file=sys.stderr)
            return 2
        print(f"# warning: reuse image not found: {image}")

    if a.apply or a.lookup:
        ids = resolve_datasets(session, a.base, refs)
        existing = fetch_existing_reuse(session, a.base, meta, a.org)
    else:
        gets = [reuse_lookup_url(a.base, a.org)] + [f"{api(a.base)}/datasets/{r}/" for r in refs if not is_object_id(r)]
        print("# dry run, nothing sent. Lookups (read-only, skipped; use --lookup): "
              + ", ".join(f"GET {u}" for u in gets))
        print("# assuming no existing reuse matches the title; dataset slugs shown as {slug:<slug>}")
        ids = [r if is_object_id(r) else f"{{slug:{r}}}" for r in refs]
        existing = None
    reqs = plan_reuse(a.base, meta, a.org, existing, ids, image)
    if not a.apply:
        print_plan(reqs)
        print("# dry run: add --apply (with UDATA_API_KEY) to send these requests")
        return 0
    result = execute(session, reqs)
    print(f"reuse: {result.get('page') or result.get('id')}")
    return 0


def main(argv: list[str] | None = None, session=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--base", required=True, help="portal root, e.g. https://www.data.gouv.fr")
    what = p.add_mutually_exclusive_group(required=True)
    what.add_argument("--meta", type=Path, help="dataset meta JSON")
    what.add_argument("--reuse", type=Path, help="reuse meta JSON, e.g. portals/data.gouv.fr/REUSE.json")
    p.add_argument("--org", help="organization id (datasets/reuses are created in it and matched within it)")
    p.add_argument("--lookup", action="store_true",
                   help="dry run: allow read-only GETs (existing dataset/reuse, dataset slugs -> ids)")
    p.add_argument("--apply", action="store_true", help="really send the requests")
    a = p.parse_args(argv)
    session, rc = open_session(a, session)
    if rc:
        return rc
    if a.reuse:
        return run_reuse(a, session)
    meta = json.loads(a.meta.read_text(encoding="utf-8"))

    existing = None
    if a.apply or a.lookup:
        existing = fetch_existing(session, a.base, meta, a.org)
    else:
        print(f"# dry run, nothing sent. Lookup (read-only, skipped; use --lookup): GET {lookup_url(a.base, a.org)}")
        print("# assuming no existing dataset matches slug/title")
    reqs = plan(a.base, meta, a.org, existing)
    if not a.apply:
        print_plan(reqs)
        print("# dry run: add --apply (with UDATA_API_KEY) to send these requests")
        return 0
    result = execute(session, reqs)
    print(f"dataset: {result.get('page') or result.get('id')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
