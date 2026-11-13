[English](README.md) | [Francais](README.fr.md)

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

The CSVs on weatheo.com also carry OpenWeather-derived columns (`owm_*`: means, normals, anomalies, day counts, highest and lowest records). They are excluded from this repository because of known quality problems in OpenWeather record, rain and sunshine values, and because their licence does not permit open redistribution. No precipitation or sunshine data is published. No Météo-France data is used.

## Limitations

Reanalysis grid cells are not station observations: values can differ from official national records, by several degrees on individual days in dense city centres, coastal or mountain locations.

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
