[English](README.md) | [Français](README.fr.md)

# Weatheo climate data

City-level temperature tables behind the [Weatheo](https://weatheo.com) climate reports, as plain CSV. Future home: <https://github.com/weatheo-com/climate-data>.

## Datasets

| Dataset | Period | Cities | Report |
|---|---|---|---|
| [`summer-2026-france`](data/summer-2026-france/) | 1 June to 31 August 2026 | 25 | [EN](https://weatheo.com/en/blog/summer-2026-france-heat-25-cities) / [FR](https://weatheo.com/fr/blog/ete-2026-canicule-25-villes-francaises) |
| [`june-2026-heatwave`](data/june-2026-heatwave/) | 15 June to 5 July 2026 | 56 | [EN](https://weatheo.com/en/blog/june-2026-heatwave-europe-in-numbers) |
| [`summer-2026-europe`](data/summer-2026-europe/) | 1 June to 31 August 2026 | 32 | [EN](https://weatheo.com/en/blog/summer-2026-europe-heat-report) |
| [`winter-2025-26`](data/winter-2025-26/) | 1 December 2025 to 28 February 2026 | 72 | [EN](https://weatheo.com/en/blog/winter-2025-26-cold-warm-72-cities) |
| [`past-12-months`](data/past-12-months/) | 12 September 2025 to August 2026 | 87 | [EN](https://weatheo.com/en/blog/past-12-months-temperature-87-cities) |

More reports: <https://weatheo.com/en/blog> (French: <https://weatheo.com/fr/blog>). Each folder has a README with the column definitions; `datapackage.json` describes all files in machine-readable form (Frictionless Data Package).

## Source and method

ERA5 reanalysis (Copernicus Climate Change Service), retrieved through the Open-Meteo Historical Weather API. Anomalies are measured against a 2011-2025 baseline. Full method: <https://weatheo.com/en/blog/methodology> (French: <https://weatheo.com/fr/blog/methodology>).

## What is not here

The CSVs on weatheo.com also carry OpenWeather-derived columns (`owm_*`: means, normals, anomalies, day counts, highest and lowest records). They are excluded from this repository because of known quality problems in OpenWeather record, rain and sunshine values, and because their licence does not permit open redistribution. The blog temperature tables above publish no precipitation or sunshine data (the municipal normals below do include ERA5-Land precipitation). No Météo-France data is used.

## Limitations

Reanalysis grid cells are not station observations: values can differ from official national records, by several degrees on individual days in dense city centres, coastal or mountain locations.

## Municipal climate normals (FR, PT, LU, RS)

Climate normals for every municipality of four countries, published by Weatheo (by CODELIO). Landing page: [Weatheo](https://weatheo.com/en/open-data). Each country has its files in `data/<CC>/` as CSV, parquet and a `datapackage.json`; they are also attached to the GitHub release v1.0.0 (`https://github.com/weatheo-com/climate-data/releases/download/v1.0.0/<file>`).

| Country | Municipalities | Code |
|---|---|---|
| France (FR) | 34,863 communes (metropolitan France and Corsica; overseas departments not included) | INSEE |
| Portugal (PT) | 308 municípios (mainland, Madeira, Azores) | DICO |
| Luxembourg (LU) | 100 communes | LAU |
| Serbia (RS) | 169 municipalities and cities (opštine i gradovi) | RZS |

Two datasets per country:

- **`<cc>_climate_normals_1991_2020`**: monthly climate normals 1991-2020 per municipality. Columns: `country`, `code`, `name`, `admin1_code`, `admin1_name`, `admin2_code`, `admin2_name`, `latitude`, `longitude`, `grid_lat`, `grid_lon`, `grid_source`, `month` (1-12), `tmean_c` (mean 2 m air temperature, °C), `precip_mm` (mean monthly precipitation, mm), `period`, `weatheo_url`.
- **`<cc>_climate_shift_1961_1990_vs_1991_2020`**: per municipality and month (1-12 and annual), the 1961-1990 value, the 1991-2020 value and the shift, for temperature (°C) and precipitation (%).

`weatheo_url` links to the Weatheo forecast page of the municipality when one exists (FR 30,631 of 34,863; PT 129 of 308; LU 4 of 100; RS 86 of 169), else it is empty.

### Method

Copernicus ERA5-Land monthly means (0.1°, about 9 km), with ERA5 monthly means (0.25°) as fallback where the ERA5-Land cell has no value (coasts). Each municipality takes the nearest grid cell to its centre point (`grid_lat`, `grid_lon`, `grid_source`). The normals are 30-year means of the monthly values. The files are built by the open scripts in `src/climate_data/` and checked by a validator script. OpenWeather, Météo-France station data and Open-Meteo are not used for these datasets.

### Limits

Values are reanalysis grid-cell values, not station observations: they can differ from official station normals, especially with altitude, on coasts and in cities.

### Place sources

| Country | Source | Licence |
|---|---|---|
| FR | "Liste des communes de France", data.gouv.fr | Licence Ouverte 2.0 |
| PT | CAOP 2025, Direção-Geral do Território | CC BY |
| LU | STATEC LAU codes, data.public.lu; coordinates from GeoNames | CC0; GeoNames CC BY 4.0 |
| RS | RZS "Opštine i gradovi", data.gov.rs; coordinates from GeoNames | "sodl" (commercial reuse to be verified); GeoNames CC BY 4.0 |

URLs, files and retrieval dates: [docs/places-sources.md](docs/places-sources.md).

### Attribution

Data licence CC BY 4.0; code MIT. Any use of these datasets must carry this notice:

> Contains modified Copernicus Climate Change Service information 2026. Neither the European Commission nor ECMWF is responsible for any use that may be made of the Copernicus information or data it contains.

### Rebuild

```sh
pip install -e .
scripts/fetch_places.sh            # raw municipality files into places/raw/<cc>/
python -m climate_data.build --country FR    # or PT, LU, RS
python -m climate_data.validate data/FR/datapackage.json
```

The build downloads ERA5-Land and ERA5 from the Copernicus Climate Data Store (needs a CDS account and `cdsapi` key) and caches them in `cache/`.

## Licence and how to cite

- Data: [CC BY 4.0](LICENSE). Credit: "Weatheo (weatheo.com), based on ERA5 data from the Copernicus Climate Change Service via Open-Meteo", with a link to the report or to <https://weatheo.com>. Upstream notices are in [LICENSE](LICENSE).
- Code (`scripts/`): MIT, see [LICENSE-CODE](LICENSE-CODE).
- Citation metadata: [CITATION.cff](CITATION.cff).
- Reproduce and check the files: `node scripts/build.mjs --check`.

## Related

- Live forecast for any row: open its `forecast_page` link.
- JSON API: <https://weatheo.com/api/v1/weather?place=fr/centre-val-de-loire/gien>
- <https://github.com/weatheo-com/github-readme-weather>
- <https://github.com/weatheo-com/weatheo-ui>
- <https://github.com/weatheo-com/mcp-server-weatheo>
