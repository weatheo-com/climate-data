[English](README.md) | [Francais](README.fr.md)

# Donnees climatiques Weatheo

Les tableaux de temperatures par ville derriere les rapports climatiques de [Weatheo](https://weatheo.com), en CSV simple. Futur depot : <https://github.com/weatheo-com/climate-data>.

## Jeux de donnees

| Jeu de donnees | Periode | Villes | Rapport |
|---|---|---|---|
| [`summer-2026-france`](data/summer-2026-france/) | 1er juin au 31 aout 2026 | 25 | [FR](https://weatheo.com/fr/blog/ete-2026-canicule-25-villes-francaises) / [EN](https://weatheo.com/en/blog/summer-2026-france-heat-25-cities) |
| [`june-2026-heatwave`](data/june-2026-heatwave/) | 15 juin au 5 juillet 2026 | 56 | [EN](https://weatheo.com/en/blog/june-2026-heatwave-europe-in-numbers) |
| [`summer-2026-europe`](data/summer-2026-europe/) | 1er juin au 31 aout 2026 | 32 | [EN](https://weatheo.com/en/blog/summer-2026-europe-heat-report) |
| [`winter-2025-26`](data/winter-2025-26/) | 1er decembre 2025 au 28 fevrier 2026 | 72 | [EN](https://weatheo.com/en/blog/winter-2025-26-cold-warm-72-cities) |
| [`past-12-months`](data/past-12-months/) | 12 septembre 2025 a aout 2026 | 87 | [EN](https://weatheo.com/en/blog/past-12-months-temperature-87-cities) |

Autres articles : <https://weatheo.com/fr/blog> (anglais : <https://weatheo.com/en/blog>). Chaque dossier contient un README avec la definition des colonnes (en anglais) ; `datapackage.json` decrit tous les fichiers de facon lisible par machine (Frictionless Data Package).

## Source et methode

Reanalyse ERA5 (Copernicus Climate Change Service), recuperee via l'API Open-Meteo Historical Weather. Les anomalies sont calculees par rapport a une reference 2011-2025. Methode complete : <https://weatheo.com/fr/blog/methodology> (anglais : <https://weatheo.com/en/blog/methodology>).

## Ce qui n'est pas ici

Les CSV de weatheo.com contiennent aussi des colonnes issues d'OpenWeather (`owm_*` : moyennes, normales, anomalies, nombres de jours, records haut et bas). Elles sont exclues de ce depot a cause de problemes de qualite connus sur les records, la pluie et l'ensoleillement d'OpenWeather, et parce que leur licence n'autorise pas la redistribution libre. Aucune donnee de precipitations ou d'ensoleillement n'est publiee. Aucune donnee Météo-France n'est utilisee.

## Limites

Les mailles de la reanalyse ne sont pas des observations de stations : les valeurs peuvent differer des records officiels nationaux, de plusieurs degres certains jours en centre-ville dense, sur la cote ou en montagne.

## Licence et citation

- Donnees : [CC BY 4.0](LICENSE). Mention : "Weatheo (weatheo.com), based on ERA5 data from the Copernicus Climate Change Service via Open-Meteo", avec un lien vers l'article ou vers <https://weatheo.com>. Les mentions des sources amont sont dans [LICENSE](LICENSE).
- Code (`scripts/`) : MIT, voir [LICENSE-CODE](LICENSE-CODE).
- Metadonnees de citation : [CITATION.cff](CITATION.cff).
- Reproduire et verifier les fichiers : `node scripts/build.mjs --check`.

## Voir aussi

- Prevision en direct pour chaque ligne : le lien de la colonne `forecast_page`.
- API JSON : <https://weatheo.com/api/v1/weather?place=fr/centre-val-de-loire/gien>
- <https://github.com/weatheo-com/github-readme-weather>
- <https://github.com/weatheo-com/weatheo-ui>
- <https://github.com/weatheo-com/mcp-server-weatheo>
