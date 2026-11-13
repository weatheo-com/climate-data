[English](README.md) | [Français](README.fr.md)

# Données climatiques Weatheo

Les tableaux de températures par ville derrière les rapports climatiques de [Weatheo](https://weatheo.com), en CSV simple. Futur dépôt : <https://github.com/weatheo-com/climate-data>.

## Jeux de données

| Jeu de données | Période | Villes | Rapport |
|---|---|---|---|
| [`summer-2026-france`](data/summer-2026-france/) | 1er juin au 31 août 2026 | 25 | [FR](https://weatheo.com/fr/blog/ete-2026-canicule-25-villes-francaises) / [EN](https://weatheo.com/en/blog/summer-2026-france-heat-25-cities) |
| [`june-2026-heatwave`](data/june-2026-heatwave/) | 15 juin au 5 juillet 2026 | 56 | [EN](https://weatheo.com/en/blog/june-2026-heatwave-europe-in-numbers) |
| [`summer-2026-europe`](data/summer-2026-europe/) | 1er juin au 31 août 2026 | 32 | [EN](https://weatheo.com/en/blog/summer-2026-europe-heat-report) |
| [`winter-2025-26`](data/winter-2025-26/) | 1er décembre 2025 au 28 février 2026 | 72 | [EN](https://weatheo.com/en/blog/winter-2025-26-cold-warm-72-cities) |
| [`past-12-months`](data/past-12-months/) | 12 septembre 2025 à août 2026 | 87 | [EN](https://weatheo.com/en/blog/past-12-months-temperature-87-cities) |

Autres articles : <https://weatheo.com/fr/blog> (anglais : <https://weatheo.com/en/blog>). Chaque dossier contient un README avec la définition des colonnes (en anglais) ; `datapackage.json` décrit tous les fichiers de façon lisible par machine (Frictionless Data Package).

## Source et méthode

Réanalyse ERA5 (Copernicus Climate Change Service), récupérée via l'API Open-Meteo Historical Weather. Les anomalies sont calculées par rapport à une référence 2011-2025. Méthode complète : <https://weatheo.com/fr/blog/methodology> (anglais : <https://weatheo.com/en/blog/methodology>).

## Ce qui n'est pas ici

Les CSV de weatheo.com contiennent aussi des colonnes issues d'OpenWeather (`owm_*` : moyennes, normales, anomalies, nombres de jours, records haut et bas). Elles sont exclues de ce dépôt à cause de problèmes de qualité connus sur les records, la pluie et l'ensoleillement d'OpenWeather, et parce que leur licence n'autorise pas la redistribution libre. Aucune donnée de précipitations ou d'ensoleillement n'est publiée. Aucune donnée Météo-France n'est utilisée.

## Limites

Les mailles de la réanalyse ne sont pas des observations de stations : les valeurs peuvent différer des records officiels nationaux, de plusieurs degrés certains jours en centre-ville dense, sur la côte ou en montagne.

## Licence et citation

- Données : [CC BY 4.0](LICENSE). Mention : « Weatheo (weatheo.com), based on ERA5 data from the Copernicus Climate Change Service via Open-Meteo », avec un lien vers l'article ou vers <https://weatheo.com>. Les mentions des sources amont sont dans [LICENSE](LICENSE).
- Code (`scripts/`) : MIT, voir [LICENSE-CODE](LICENSE-CODE).
- Métadonnées de citation : [CITATION.cff](CITATION.cff).
- Reproduire et vérifier les fichiers : `node scripts/build.mjs --check`.

## Voir aussi

- Prévision en direct pour chaque ligne : le lien de la colonne `forecast_page`.
- API JSON : <https://weatheo.com/api/v1/weather?place=fr/centre-val-de-loire/gien>
- <https://github.com/weatheo-com/github-readme-weather>
- <https://github.com/weatheo-com/weatheo-ui>
- <https://github.com/weatheo-com/mcp-server-weatheo>
