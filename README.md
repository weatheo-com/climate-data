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

## Municipal climate normals (FR, DE, GB, PT, LU, RS)

Climate normals for every municipality of six countries, published by Weatheo (by CODELIO). Landing page: [Weatheo](https://weatheo.com/en/open-data). Each country has its files in `data/<CC>/` as CSV, parquet and a `datapackage.json`; they are also attached to the GitHub release v1.1.0 (`https://github.com/weatheo-com/climate-data/releases/download/v1.1.0/<file>`; the v1.0.0 files for FR, PT, LU and RS stay valid). The release names the files in lower case, with each country's datapackage as `<cc>_datapackage.json`. The two France CSVs (60-70 MB each) are only on the release, as they are too large for git; the France parquet files are in the repository.

| Country | Municipalities | Code |
|---|---|---|
| France (FR) | 34,734 communes (metropolitan France and Corsica; overseas departments not included) | INSEE |
| Portugal (PT) | 308 municípios (mainland, Madeira, Azores) | DICO |
| Luxembourg (LU) | 100 communes | LAU |
| Serbia (RS) | 169 municipalities and cities (opštine i gradovi) | RZS |
| Germany (DE) | 10,949 Gemeinden (AGS; BKG VG250-EW, dl-de/by-2-0) | AGS |
| United Kingdom (GB) | 8,545 built-up areas (BUA22CD; ONS, OGL v3; no Northern Ireland) | BUA22CD |

Two datasets per country:

- **`<cc>_climate_normals_1991_2020`**: monthly climate normals 1991-2020 per municipality. Columns: `country`, `code`, `name`, `admin1_code`, `admin1_name`, `admin2_code`, `admin2_name`, `latitude`, `longitude`, `grid_lat`, `grid_lon`, `grid_source`, `elevation_m` (m), `grid_elevation_m` (m), `month` (1-12), `tmean_c` (mean 2 m air temperature, °C), `precip_mm` (mean monthly precipitation, mm), `period`, `weatheo_url`.
- **`<cc>_climate_shift_1961_1990_vs_1991_2020`**: per municipality and month (1-12 and annual), the 1961-1990 value, the 1991-2020 value and the shift, for temperature (°C) and precipitation (%).

`weatheo_url` links to the Weatheo forecast page of the municipality when one exists (FR 30,631 of 34,734; PT 139 of 308; LU 4 of 100; RS 86 of 169; DE 990 of 10,949; GB 708 of 8,545), else it is empty.

### Method

Copernicus ERA5-Land monthly means (0.1°, about 9 km), with ERA5 monthly means (0.25°) as fallback where the ERA5-Land cell has no value (coasts). Each municipality takes the nearest grid cell to its reference point (town hall for France, municipal seat for Portugal, BKG municipal point for Germany, ONS built-up area centroid for Great Britain) (`grid_lat`, `grid_lon`, `grid_source`). Temperatures are adjusted for altitude: each value is moved from the grid cell's model elevation (`grid_elevation_m`, ERA5-Land orography, ECMWF) to the elevation of the municipality's reference point (`elevation_m`, from the Copernicus DEM GLO-90) with a fixed lapse rate of 6.5 °C per km: `t = t_cell + 0.0065 × (grid_elevation_m − elevation_m)`. Precipitation is not adjusted. The temperature shift between the two periods does not depend on this adjustment. The normals are 30-year means of the monthly values. The files are built by the open scripts in `src/climate_data/` and checked by a validator script. OpenWeather, Météo-France station data and Open-Meteo are not used for these datasets.

### Limits

Values are reanalysis grid-cell values, not station observations: they can differ from official station normals, mostly near coasts, in cities and in steep terrain.

### Place sources

| Country | Source | Licence |
|---|---|---|
| FR | "Liste des communes de France", data.gouv.fr | Licence Ouverte 2.0 |
| PT | CAOP 2025, Direção-Geral do Território; municipal seat points from GeoNames | CC BY; CC BY 4.0 |
| LU | STATEC LAU codes, data.public.lu; coordinates from GeoNames | CC0; GeoNames CC BY 4.0 |
| RS | RZS "Opštine i gradovi", data.gov.rs; coordinates from GeoNames | SODL (commercial reuse allowed with source, download date 2026-11-13, address and changes stated); GeoNames CC BY 4.0 |
| DE | VG250-EW, BKG (https://gdz.bkg.bund.de/index.php/default/verwaltungsgebiete-1-250-000-mit-einwohnerzahlen-ebenen-stand-31-12-vg250-ew-ebenen-31-12.html); municipal point from BKG | dl-de/by-2-0 (Datenlizenz Deutschland Namensnennung 2.0). © GeoBasis-DE / BKG (2026), data changed (climate values added) |
| GB | ONS Built-up areas (December 2022), https://geoportal.statistics.gov.uk/; centroid of the built-up area | OGL v3.0. Source: Office for National Statistics licensed under the Open Government Licence v.3.0. Contains OS data © Crown copyright and database right 2022 |

URLs, files and retrieval dates: [docs/places-sources.md](docs/places-sources.md).

### Attribution

Data licence CC BY 4.0; code MIT. Any use of these datasets must carry this notice:

> Contains modified Copernicus Climate Change Service information 2026. Neither the European Commission nor ECMWF is responsible for any use that may be made of the Copernicus information or data it contains.
>
> Copernicus DEM GLO-90 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA.

### Rebuild

```sh
pip install -e .
scripts/fetch_places.sh            # raw municipality files into places/raw/<cc>/
python -m climate_data.build --country FR    # or PT, LU, RS
python -m climate_data.validate data/FR/datapackage.json
```

The build downloads ERA5-Land and ERA5 from the Copernicus Climate Data Store (needs a CDS account and `cdsapi` key) and caches them in `cache/`.

## City climate: daily, monthly and annual (GB, DE, FR, PT, LU, RS)

Daily weather history, monthly climate and annual indicators for the largest cities of six countries (345 cities), 1950-2025, published by Weatheo (by CODELIO). France and Germany: the 100 most populous municipalities by official population (France: INSEE population from the "Liste des communes de France" file on data.gouv.fr, Licence Ouverte 2.0; Germany: BKG VG250-EW, © GeoBasis-DE / BKG (2026), dl-de/by-2-0, data changed (climate values added)). One point per municipality (city districts such as the Paris arrondissements are not separate cities); names are the official municipality names (Saint-Denis, Dunkerque, München, Köln); the point and time zone come from GeoNames. Great Britain (100), Portugal (20), Serbia (20) and Luxembourg (5): the most populous GeoNames (cities5000, CC BY 4.0) places, skipping a place that lies in the same 0.1° grid cell and district as a larger one. The `population` column is the official municipal population in France and Germany and the GeoNames population elsewhere; `name` is the official name in FR and DE, the GeoNames name elsewhere. Files are attached to the GitHub release v1.1.0 (`https://github.com/weatheo-com/climate-data/releases/download/v1.1.0/<file>`). Pages: [daily](https://weatheo.com/en/open-data/daily-weather-history-cities), [monthly](https://weatheo.com/en/open-data/monthly-climate-degree-days-cities), [annual](https://weatheo.com/en/open-data/annual-climate-indicators-cities).

| Dataset | Files per country (`<cc>` = gb, de, fr, pt, lu, rs) |
|---|---|
| Daily, 2 or 3 January 1950 to 31 December 2025 | `<cc>_city_daily_weather_1950_2025.parquet`, `<cc>_city_daily_weather_1950_2025_csv.zip` (one CSV per city), `<cc>_cities.csv`, `<cc>_cities_datapackage.json` |
| Monthly, February 1950 to December 2025 | `<cc>_city_monthly_climate_1950_2025.csv` and `.parquet`, `<cc>_city_climate_normals_1991_2020.csv` |
| Annual, 1951-2025 | `<cc>_city_annual_climate_indicators_1951_2025.csv`, trend columns in `<cc>_cities.csv` |

Columns:

- **Daily**: `country`, `city_id` (GeoNames id), `name`, `date`, `tmean_c`, `tmin_c`, `tmax_c` (°C), `precip_mm` (mm), `wind_mean_kmh`, `wind_max_kmh` (km/h, hourly means, not gusts), `solar_kwh_m2` (kWh/m²). 27,758 rows per city in GB and PT (2 January 1950 to 31 December 2025) and 27,757 in FR, DE, LU and RS (from 3 January 1950): the hourly series are downloaded from 00:00 UTC on 2 January 1950 and only complete local days are kept.
- **Monthly**: one row per city, year and month (complete months): `tmean_c`, `tmin_mean_c`, `tmax_mean_c`, `tmin_abs_c`, `tmax_abs_c` (°C), `precip_mm`, `wet_days` (>= 1 mm), `frost_days`, `hdd_15_5`, `hdd_18`, `cdd_18`, `cdd_22`, `gtz_20_15` (degree days), `solar_kwh_m2`, `wind_mean_kmh`. The normals file has 12 rows per city: `tmean_c`, `tmin_c`, `tmax_c`, `precip_mm`, `wet_days`, `frost_days`, `summer_days`, `hot_days`, `solar_kwh_m2_day`, `wind_mean_kmh`, `hdd_15_5`, `hdd_18`, `cdd_18`.
- **Annual** (full years only): `year`, `tmean_c`, `tmean_anomaly_c` (vs 1991-2020), `precip_mm`, `precip_anomaly_pct`, `wet_days`, `heavy_rain_days` (>= 20 mm), `max_1day_precip_mm`, `frost_days` (tmin < 0), `ice_days` (tmax < 0), `summer_days` (tmax >= 25), `hot_days` (tmax >= 30), `tropical_nights` (tmin >= 20), `tmax_abs_c`, `tmin_abs_c`, `hdd_15_5`, `hdd_18`, `cdd_18`, `cdd_22`, `rank_warmest`. Trend columns in `<cc>_cities.csv`: `tmean_annual_c`, `precip_annual_mm`, `trend_c_per_decade_1951_2025`, `trend_c_per_decade_1981_2025`, `warmest_year`, `coldest_year`, `wettest_year`, `driest_year`.

### Method

Copernicus ERA5-Land hourly reanalysis (`reanalysis-era5-land-timeseries`, 0.1° grid), nearest cell to the city point, one request per city. Days are local civil days (IANA time zone), only complete days. Temperatures are adjusted for altitude at 6.5 °C per km; precipitation is not adjusted. Monthly and annual files are derived from the daily file.

### Limits

Values are grid-cell reanalysis values, not station measurements. Hot days in city centres are undercounted. Degree days differ from figures published by national services.

### Place source

- Points and time zones: GeoNames cities5000, CC BY 4.0.
- French names and populations: INSEE communes list ("Liste des communes de France", data.gouv.fr), Licence Ouverte 2.0.
- German names and populations: BKG VG250-EW, © GeoBasis-DE / BKG (2026), dl-de/by-2-0, data changed (climate values added).

Data licence CC BY 4.0, code MIT. Notice to carry:

> Contains modified Copernicus Climate Change Service information 2026. Neither the European Commission nor ECMWF is responsible for any use that may be made of the Copernicus information or data it contains.

### Rebuild

```sh
python -m climate_data.cities          # pick the cities from GeoNames
python -m climate_data.fetch_timeseries --country FR    # ERA5-Land time series (CDS key needed), or GB, DE, PT, LU, RS
python -m climate_data.build_cities --country FR
```

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
