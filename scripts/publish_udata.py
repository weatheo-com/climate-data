#!/usr/bin/env python3
"""Create or update a dataset on a uData portal (API v1), dry-run by default.

Portals: https://www.data.gouv.fr, https://dados.gov.pt, https://data.public.lu,
https://data.gov.rs (all uData, API v1 under /api/1/).

    python scripts/publish_udata.py --base https://www.data.gouv.fr \
        --meta portals/example/FR-A.json [--org <org id>] [--lookup] [--apply]

Without --apply nothing is sent: the script prints every request it would make
with its JSON payload. --lookup allows read-only GETs in a dry run to decide
create vs update. With --apply the API key is read from env UDATA_API_KEY and
sent as the X-API-KEY header.

Meta file keys: slug, title, description, tags, license (uData licence id, e.g.
"cc-by"; list at /api/1/datasets/licenses/), frequency (enum from
/api/1/datasets/frequencies/, e.g. "irregular"), optional temporal_coverage
{start, end}, resources [{title, url, format, mime?, type?, description?}]
pointing at remote files (GitHub release assets).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

DATASET_FIELDS = ("title", "description", "tags", "license", "frequency", "temporal_coverage")
RESOURCE_FIELDS = ("title", "url", "format", "mime", "type", "description")


def api(base: str) -> str:
    return base.rstrip("/") + "/api/1"


def dataset_payload(meta: dict, org: str | None) -> dict:
    payload = {k: meta[k] for k in DATASET_FIELDS if k in meta}
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


def fetch_existing(session, base: str, meta: dict, org: str | None) -> dict | None:
    """Read-only lookup of a matching dataset in the org (or the key owner's datasets)."""
    r = session.get(lookup_url(base, org), timeout=60)
    r.raise_for_status()
    body = r.json()
    items = body.get("data", body) if isinstance(body, dict) else body
    found = find_existing(items, meta)
    if found is None:
        return None
    full = session.get(f"{api(base)}/datasets/{found['id']}/", timeout=60)
    full.raise_for_status()
    return full.json()


def print_plan(reqs: list[dict], out=None) -> None:
    out = out or sys.stdout
    for r in reqs:
        print(f"{r['method']} {r['url']}", file=out)
        print(json.dumps(r["json"], ensure_ascii=False, indent=2), file=out)


def execute(session, reqs: list[dict]) -> dict:
    new_id = None
    result: dict = {}
    for r in reqs:
        url = r["url"].replace("{new_dataset_id}", new_id or "{new_dataset_id}")
        if "{new_dataset_id}" in url:
            raise RuntimeError("dataset id unknown before resource request")
        resp = session.request(r["method"], url, json=r["json"], timeout=120)
        resp.raise_for_status()
        data = resp.json() if resp.content else {}
        if not result:
            result = data
            new_id = data.get("id")
        print(f"{r['method']} {url} -> {resp.status_code}")
    return result


def main(argv: list[str] | None = None, session=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--base", required=True, help="portal root, e.g. https://www.data.gouv.fr")
    p.add_argument("--meta", required=True, type=Path)
    p.add_argument("--org", help="organization id (datasets are created in it and matched within it)")
    p.add_argument("--lookup", action="store_true", help="dry run: allow read-only GETs to find an existing dataset")
    p.add_argument("--apply", action="store_true", help="really send the requests")
    a = p.parse_args(argv)
    meta = json.loads(a.meta.read_text(encoding="utf-8"))

    if a.apply or a.lookup:
        if session is None:
            import requests

            session = requests.Session()
        key = os.environ.get("UDATA_API_KEY")
        if a.apply and not key:
            print("UDATA_API_KEY is not set", file=sys.stderr)
            return 2
        if key:
            session.headers.update({"X-API-KEY": key})

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
