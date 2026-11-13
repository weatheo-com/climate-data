# Zenodo posting (owner checklist)

1. Create a Zenodo account (zenodo.org) and, to test first, one on sandbox.zenodo.org.
2. Applications > Personal access tokens: create a token with scopes deposit:write and deposit:actions.
3. `export ZENODO_SANDBOX_TOKEN=...` (sandbox) and `export ZENODO_TOKEN=...` (production).
4. Build the data (data/<CC>/ for FR PT LU RS), and check the release v1.0.0 exists.
5. Dry run (prints requests, sends nothing), from the climate-data repo root:

```
python scripts/publish_zenodo.py --meta portals/zenodo/ZEN-A.json --dry-run \
  --files data/*/*_climate_normals_1991_2020.csv data/*/*_climate_normals_1991_2020.parquet data/*/datapackage.json
python scripts/publish_zenodo.py --meta portals/zenodo/ZEN-B.json --dry-run \
  --files data/*/*_climate_shift_1961_1990_vs_1991_2020.csv data/*/*_climate_shift_1961_1990_vs_1991_2020.parquet data/*/datapackage.json
```

6. Sandbox draft: same commands without `--dry-run`. Check the draft on sandbox.zenodo.org.
7. Production draft: add `--production`. Review in the Zenodo UI. Publishing is irreversible: add `--publish` only after the owner OKs it.

Notes: with several data/<CC>/datapackage.json in --files the script uploads each one as <CC>_datapackage.json (Zenodo keeps one file per name; any other duplicate file name stops the script before anything is sent). Fallback: upload one combined datapackage.json at repo root instead.
The script sets creator "Weatheo (by CODELIO)" and license cc-by-4.0; related_identifiers come from the `zenodo` key in each JSON (it replaces the script defaults, repo is isSupplementTo).
Also the CSV/Parquet names must differ per country (prefix <CC>_); the sources of RS data need the commercial-reuse licence check before publishing.
