"""One-off CDS check: 2020 ERA5-Land monthly means (t2m, tp) over Luxembourg into cache/.

Needs a CDS key in ~/.cdsapirc (or CDSAPI_URL / CDSAPI_KEY). Run from the repo root:
    .venv/bin/python scripts/cds_check.py
"""

from pathlib import Path

import xarray as xr

from climate_data.fetch_cds import fetch

DATASET = "reanalysis-era5-land-monthly-means"
REQUEST = {
    "product_type": "monthly_averaged_reanalysis",
    "variable": ["2m_temperature", "total_precipitation"],
    "month": [f"{m:02d}" for m in range(1, 13)],
    "time": ["00:00"],
}
BBOX = (50.2, 5.7, 49.4, 6.6)  # N, W, S, E


def main() -> None:
    cache = Path(__file__).resolve().parent.parent / "cache"
    paths = fetch(DATASET, REQUEST, BBOX, [2020], cache)
    for p in paths:
        print(p, p.stat().st_size, "bytes")
        with xr.open_dataset(p) as ds:
            print("dims:", dict(ds.sizes))
            print("coords:", list(ds.coords))
            for name, var in ds.data_vars.items():
                print(f"var {name}: dims={var.dims} units={var.attrs.get('units')}")


if __name__ == "__main__":
    main()
