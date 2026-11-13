#!/usr/bin/env python3
"""Create a Zenodo draft deposition with files; publish only with --publish.

    python scripts/publish_zenodo.py --meta portals/example/FR-A.json \
        --files data/FR/*.csv data/FR/datapackage.json [--production] [--publish] [--dry-run]

sandbox.zenodo.org by default; --production targets zenodo.org. Token from env
ZENODO_TOKEN (production) or ZENODO_SANDBOX_TOKEN, then ZENODO_TOKEN (sandbox).
Without a token (or with --dry-run) the requests and metadata are printed and
nothing is sent.

Meta keys used: title, description, tags (-> keywords), optional version,
publication_date, zenodo (dict merged into the metadata last, so its
related_identifiers replace the defaults; default repo relation isSupplementTo).

Files keep their names in the bucket, except that with several
data/<CC>/datapackage.json each one is uploaded as <CC>_datapackage.json; any
other duplicate file name is an error (Zenodo keeps one file per name).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

SANDBOX = "https://sandbox.zenodo.org/api"
PRODUCTION = "https://zenodo.org/api"
REPO_URL = "https://github.com/weatheo-com/climate-data"
OPEN_DATA_URL = "https://weatheo.com/en/open-data"
CREATOR = "Weatheo (by CODELIO)"


def metadata(meta: dict) -> dict:
    md = {
        "upload_type": "dataset",
        "title": meta["title"],
        "description": meta.get("description", meta["title"]).replace("\n", "<br>"),
        "creators": [{"name": CREATOR}],
        "license": "cc-by-4.0",
        "access_right": "open",
        "keywords": list(meta.get("tags", [])),
        "related_identifiers": [
            {"identifier": REPO_URL, "relation": "isSupplementTo", "scheme": "url", "resource_type": "software"},
            {"identifier": OPEN_DATA_URL, "relation": "isDocumentedBy", "scheme": "url"},
        ],
    }
    for k in ("version", "publication_date"):
        if meta.get(k):
            md[k] = meta[k]
    md.update(meta.get("zenodo", {}))
    return md


def token_for(production: bool, env=os.environ) -> str | None:
    if production:
        return env.get("ZENODO_TOKEN")
    return env.get("ZENODO_SANDBOX_TOKEN") or env.get("ZENODO_TOKEN")


def upload_names(files: list[Path]) -> list[tuple[Path, str]]:
    """(path, bucket name) per file. Several datapackage.json -> <parent dir>_datapackage.json
    (data/FR/datapackage.json -> FR_datapackage.json). Raises ValueError on any other duplicate."""
    several = sum(f.name == "datapackage.json" for f in files) > 1
    out = []
    for f in files:
        name = f.name
        if several and name == "datapackage.json" and f.parent.name:
            name = f"{f.parent.name}_datapackage.json"
        out.append((f, name))
    counts = Counter(name for _, name in out)
    dups = sorted(n for n, c in counts.items() if c > 1)
    if dups:
        detail = "; ".join(f"{n}: {', '.join(str(f) for f, m in out if m == n)}" for n in dups)
        raise ValueError(f"duplicate upload file names (Zenodo keeps one file per name): {detail}")
    return out


def plan(api: str, meta: dict, files: list[Path], publish: bool) -> list[dict]:
    """Ordered requests (pure). {bucket} and {id} come from the create response."""
    reqs = [{"method": "POST", "url": f"{api}/deposit/depositions", "json": {}}]
    for f, name in upload_names(files):
        reqs.append({"method": "PUT", "url": f"{{bucket}}/{name}", "file": str(f)})
    reqs.append({"method": "PUT", "url": f"{api}/deposit/depositions/{{id}}", "json": {"metadata": metadata(meta)}})
    if publish:
        reqs.append({"method": "POST", "url": f"{api}/deposit/depositions/{{id}}/actions/publish", "json": None})
    return reqs


def print_plan(reqs: list[dict], out=None) -> None:
    out = out or sys.stdout
    for r in reqs:
        print(f"{r['method']} {r['url']}", file=out)
        if "file" in r:
            print(f"  <body: contents of {r['file']}>", file=out)
        elif r.get("json") is not None:
            print(json.dumps(r["json"], ensure_ascii=False, indent=2), file=out)


def execute(session, reqs: list[dict]) -> dict:
    ids = {}
    dep: dict = {}
    for r in reqs:
        url = r["url"].format(**ids) if ids else r["url"]
        if "file" in r:
            with open(r["file"], "rb") as fh:
                resp = session.put(url, data=fh, timeout=600)
        else:
            resp = session.request(r["method"], url, json=r["json"], timeout=120)
        resp.raise_for_status()
        print(f"{r['method']} {url} -> {resp.status_code}")
        if not ids:
            dep = resp.json()
            ids = {"id": dep["id"], "bucket": dep["links"]["bucket"]}
        elif r["method"] != "PUT" or "file" not in r:
            dep = resp.json()
    return dep


def main(argv: list[str] | None = None, session=None, env=os.environ) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--meta", required=True, type=Path)
    p.add_argument("--files", nargs="+", required=True, type=Path)
    p.add_argument("--production", action="store_true", help="zenodo.org instead of sandbox.zenodo.org")
    p.add_argument("--publish", action="store_true", help="publish the draft (irreversible on zenodo.org)")
    p.add_argument("--dry-run", action="store_true", help="print the requests even when a token is set")
    a = p.parse_args(argv)
    meta = json.loads(a.meta.read_text(encoding="utf-8"))
    api = PRODUCTION if a.production else SANDBOX
    try:
        reqs = plan(api, meta, a.files, a.publish)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    token = token_for(a.production, env)
    if a.dry_run or not token:
        why = "--dry-run" if a.dry_run else "no token (ZENODO_TOKEN / ZENODO_SANDBOX_TOKEN)"
        print(f"# dry run ({why}), nothing sent")
        print_plan(reqs)
        return 0
    missing = [str(f) for f in a.files if not f.is_file()]
    if missing:
        print(f"missing files: {missing}", file=sys.stderr)
        return 2
    if session is None:
        import requests

        session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}"})
    dep = execute(session, reqs)
    state = "published" if a.publish else "draft"
    print(f"{state}: {dep.get('links', {}).get('html') or dep.get('id')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
