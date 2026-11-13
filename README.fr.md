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

Les CSV de weatheo.com contiennent aussi des colonnes issues d'OpenWeather (`owm_*` : moyennes, normales, anomalies, nombres de jours, records haut et bas). Elles sont exclues de ce dépôt à cause de problèmes de qualité connus sur les records, la pluie et l'ensoleillement d'OpenWeather, et parce que leur licence n'autorise pas la redistribution libre. Les tableaux de températures des articles ci-dessus ne publient aucune donnée de précipitations ou d'ensoleillement (les normales par commune ci-dessous incluent les précipitations ERA5-Land). Aucune donnée Météo-France n'est utilisée.

## Limites

Les mailles de la réanalyse ne sont pas des observations de stations : les valeurs peuvent différer des records officiels nationaux, de plusieurs degrés certains jours en centre-ville dense, sur la côte ou en montagne.

## Normales climatiques par commune (FR, DE, GB, PT, LU, RS)

Normales climatiques pour chaque commune de six pays, publiées par Weatheo (by CODELIO). Page de présentation : [Weatheo](https://weatheo.com/fr/open-data). Chaque pays a ses fichiers dans `data/<CC>/` en CSV, parquet et `datapackage.json` ; ils sont aussi joints à la release GitHub v1.1.0 (`https://github.com/weatheo-com/climate-data/releases/download/v1.1.0/<fichier>`; les fichiers v1.0.0 de FR, PT, LU et RS restent valables). Les deux CSV de la France (60 à 70 Mo chacun) ne sont que sur la release, trop lourds pour git ; les fichiers parquet de la France sont dans le dépôt.

| Pays | Communes | Code |
|---|---|---|
| France (FR) | 34 734 communes (France métropolitaine et Corse ; départements d'outre-mer non inclus) | INSEE |
| Portugal (PT) | 308 municípios (continent, Madère, Açores) | DICO |
| Luxembourg (LU) | 100 communes | LAU |
| Serbie (RS) | 169 municipalités et villes (opštine i gradovi) | RZS |
| Allemagne (DE) | 10 949 Gemeinden (AGS ; BKG VG250-EW, dl-de/by-2-0) | AGS |
| Royaume-Uni (GB) | 8 545 zones bâties (BUA22CD ; ONS, OGL v3 ; sans l'Irlande du Nord) | BUA22CD |

Deux jeux de données par pays :

- **`<cc>_climate_normals_1991_2020`** : normales mensuelles 1991-2020 par commune. Colonnes : `country`, `code`, `name`, `admin1_code`, `admin1_name`, `admin2_code`, `admin2_name`, `latitude`, `longitude`, `grid_lat`, `grid_lon`, `grid_source`, `elevation_m` (m), `grid_elevation_m` (m), `month` (1-12), `tmean_c` (température moyenne de l'air à 2 m, °C), `precip_mm` (précipitations mensuelles moyennes, mm), `period`, `weatheo_url`.
- **`<cc>_climate_shift_1961_1990_vs_1991_2020`** : par commune et par mois (1-12 et année), la valeur 1961-1990, la valeur 1991-2020 et l'écart, pour la température (°C) et les précipitations (%).

`weatheo_url` renvoie vers la page de prévisions Weatheo de la commune quand elle existe (FR 30 631 sur 34 734 ; PT 139 sur 308 ; LU 4 sur 100 ; RS 86 sur 169 ; DE 990 sur 10 949 ; GB 708 sur 8 545), sinon elle est vide.

### Méthode

Moyennes mensuelles Copernicus ERA5-Land (0,1°, environ 9 km), avec les moyennes mensuelles ERA5 (0,25°) en secours là où la maille ERA5-Land n'a pas de valeur (côtes). Chaque commune prend la maille la plus proche de son point de référence (la mairie pour la France, le siège municipal pour le Portugal, point municipal du BKG pour l'Allemagne, centroïde de la zone bâtie ONS pour la Grande-Bretagne) (`grid_lat`, `grid_lon`, `grid_source`). Les températures sont corrigées de l'altitude : chaque valeur est ramenée de l'altitude du modèle de la maille (`grid_elevation_m`, orographie ERA5-Land d'ECMWF) à l'altitude du point de référence de la commune (`elevation_m`, issue du Copernicus DEM GLO-90) avec un gradient fixe de 6,5 °C par km : `t = t_cell + 0,0065 × (grid_elevation_m − elevation_m)`. Les précipitations ne sont pas corrigées. L'écart de température entre les deux périodes ne dépend pas de cette correction. Les normales sont des moyennes sur 30 ans des valeurs mensuelles. Les fichiers sont produits par les scripts ouverts de `src/climate_data/` et contrôlés par un script de validation. Ni OpenWeather, ni les données de stations Météo-France, ni Open-Meteo ne sont utilisés pour ces jeux de données.

### Limites

Ce sont des valeurs de mailles de réanalyse, pas des observations de stations : elles peuvent différer des normales officielles des stations, surtout près des côtes, en ville et en relief accidenté.

### Sources des communes

| Pays | Source | Licence |
|---|---|---|
| FR | « Liste des communes de France », data.gouv.fr | Licence Ouverte 2.0 |
| PT | CAOP 2025, Direção-Geral do Território ; points des sièges municipaux GeoNames | CC BY ; CC BY 4.0 |
| LU | Codes LAU du STATEC, data.public.lu ; coordonnées GeoNames | CC0 ; GeoNames CC BY 4.0 |
| RS | RZS « Opštine i gradovi », data.gov.rs ; coordonnées GeoNames | SODL (réutilisation commerciale permise en citant la source, la date de téléchargement 13/11/2026, l'adresse et les modifications) ; GeoNames CC BY 4.0 |
| DE | VG250-EW, BKG (https://gdz.bkg.bund.de/index.php/default/verwaltungsgebiete-1-250-000-mit-einwohnerzahlen-ebenen-stand-31-12-vg250-ew-ebenen-31-12.html) ; point municipal du BKG | dl-de/by-2-0 (Datenlizenz Deutschland Namensnennung 2.0). © GeoBasis-DE / BKG (2026), data changed (climate values added) |
| GB | ONS Built-up areas (décembre 2022), https://geoportal.statistics.gov.uk/ ; centroïde de la zone bâtie | OGL v3.0. Source: Office for National Statistics licensed under the Open Government Licence v.3.0. Contains OS data © Crown copyright and database right 2022 |

URL, fichiers et dates de récupération : [docs/places-sources.md](docs/places-sources.md).

### Attribution

Licence des données CC BY 4.0 ; code MIT. Toute utilisation de ces données doit reprendre cette mention :

> Contains modified Copernicus Climate Change Service information 2026. Neither the European Commission nor ECMWF is responsible for any use that may be made of the Copernicus information or data it contains.
>
> Copernicus DEM GLO-90 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA.

### Reconstruire

```sh
pip install -e .
scripts/fetch_places.sh            # fichiers bruts des communes dans places/raw/<cc>/
python -m climate_data.build --country FR    # ou PT, LU, RS
python -m climate_data.validate data/FR/datapackage.json
```

La construction télécharge ERA5-Land et ERA5 depuis le Copernicus Climate Data Store (compte CDS et clé `cdsapi` nécessaires) et les met en cache dans `cache/`.

## Climat par ville : quotidien, mensuel et annuel (GB, DE, FR, PT, LU, RS)

Historique météo quotidien, climat mensuel et indicateurs annuels pour les plus grandes villes de six pays (345 villes), 1950-2025, publiés par Weatheo (by CODELIO). France et Allemagne : les 100 communes les plus peuplées selon la population officielle (France : population INSEE du fichier « Liste des communes de France » sur data.gouv.fr, Licence Ouverte 2.0 ; Allemagne : BKG VG250-EW, © GeoBasis-DE / BKG (2026), dl-de/by-2-0, data changed (climate values added)). Un point par commune (les arrondissements de Paris ne sont pas des villes distinctes) ; les noms sont les noms officiels des communes (Saint-Denis, Dunkerque, München, Köln) ; le point et le fuseau horaire viennent de GeoNames. Grande-Bretagne (100), Portugal (20), Serbie (20) et Luxembourg (5) : les lieux GeoNames (cities5000, CC BY 4.0) les plus peuplés, en écartant un lieu situé dans la même maille de 0,1° et le même district qu'un lieu plus grand. La colonne `population` est la population municipale officielle en France et en Allemagne, celle de GeoNames ailleurs ; `name` est le nom officiel en FR et DE, celui de GeoNames ailleurs. Les fichiers sont joints à la release GitHub v1.1.0 (`https://github.com/weatheo-com/climate-data/releases/download/v1.1.0/<fichier>`). Pages : [quotidien](https://weatheo.com/fr/open-data/daily-weather-history-cities), [mensuel](https://weatheo.com/fr/open-data/monthly-climate-degree-days-cities), [annuel](https://weatheo.com/fr/open-data/annual-climate-indicators-cities).

| Jeu de données | Fichiers par pays (`<cc>` = gb, de, fr, pt, lu, rs) |
|---|---|
| Quotidien, du 2 ou 3 janvier 1950 au 31 décembre 2025 | `<cc>_city_daily_weather_1950_2025.parquet`, `<cc>_city_daily_weather_1950_2025_csv.zip` (un CSV par ville), `<cc>_cities.csv`, `<cc>_cities_datapackage.json` |
| Mensuel, février 1950 à décembre 2025 | `<cc>_city_monthly_climate_1950_2025.csv` et `.parquet`, `<cc>_city_climate_normals_1991_2020.csv` |
| Annuel, 1951-2025 | `<cc>_city_annual_climate_indicators_1951_2025.csv`, colonnes de tendance dans `<cc>_cities.csv` |

Colonnes :

- **Quotidien** : `country`, `city_id` (identifiant GeoNames), `name`, `date`, `tmean_c`, `tmin_c`, `tmax_c` (°C), `precip_mm` (mm), `wind_mean_kmh`, `wind_max_kmh` (km/h, moyennes horaires, pas des rafales), `solar_kwh_m2` (kWh/m²). 27 758 lignes par ville pour GB et PT (du 2 janvier 1950 au 31 décembre 2025) et 27 757 pour FR, DE, LU et RS (à partir du 3 janvier 1950) : les séries horaires sont téléchargées à partir du 2 janvier 1950 à 00:00 UTC et seuls les jours locaux complets sont gardés.
- **Mensuel** : une ligne par ville, année et mois (mois complets) : `tmean_c`, `tmin_mean_c`, `tmax_mean_c`, `tmin_abs_c`, `tmax_abs_c` (°C), `precip_mm`, `wet_days` (>= 1 mm), `frost_days`, `hdd_15_5`, `hdd_18`, `cdd_18`, `cdd_22`, `gtz_20_15` (degrés-jours), `solar_kwh_m2`, `wind_mean_kmh`. Le fichier des normales a 12 lignes par ville : `tmean_c`, `tmin_c`, `tmax_c`, `precip_mm`, `wet_days`, `frost_days`, `summer_days`, `hot_days`, `solar_kwh_m2_day`, `wind_mean_kmh`, `hdd_15_5`, `hdd_18`, `cdd_18`.
- **Annuel** (années complètes seulement) : `year`, `tmean_c`, `tmean_anomaly_c` (par rapport à 1991-2020), `precip_mm`, `precip_anomaly_pct`, `wet_days`, `heavy_rain_days` (>= 20 mm), `max_1day_precip_mm`, `frost_days` (tmin < 0), `ice_days` (tmax < 0), `summer_days` (tmax >= 25), `hot_days` (tmax >= 30), `tropical_nights` (tmin >= 20), `tmax_abs_c`, `tmin_abs_c`, `hdd_15_5`, `hdd_18`, `cdd_18`, `cdd_22`, `rank_warmest`. Colonnes de tendance dans `<cc>_cities.csv` : `tmean_annual_c`, `precip_annual_mm`, `trend_c_per_decade_1951_2025`, `trend_c_per_decade_1981_2025`, `warmest_year`, `coldest_year`, `wettest_year`, `driest_year`.

### Méthode

Réanalyse horaire Copernicus ERA5-Land (`reanalysis-era5-land-timeseries`, grille de 0,1°), maille la plus proche du point de la ville, une requête par ville. Les jours sont des jours civils locaux (fuseau IANA), jours complets seulement. Les températures sont corrigées de l'altitude à 6,5 °C par km ; les précipitations ne sont pas corrigées. Les fichiers mensuels et annuels sont dérivés du fichier quotidien.

### Limites

Valeurs de réanalyse par maille, pas des mesures de stations. Les jours de chaleur sont sous-estimés dans les centres-villes. Les degrés-jours diffèrent des chiffres publiés par les services nationaux.

### Source des villes

- Points et fuseaux horaires : GeoNames cities5000, CC BY 4.0.
- Noms et populations français : liste des communes INSEE (« Liste des communes de France », data.gouv.fr), Licence Ouverte 2.0.
- Noms et populations allemands : BKG VG250-EW, © GeoBasis-DE / BKG (2026), dl-de/by-2-0, data changed (climate values added).

Données sous licence CC BY 4.0, code MIT. Mention à reprendre :

> Contains modified Copernicus Climate Change Service information 2026. Neither the European Commission nor ECMWF is responsible for any use that may be made of the Copernicus information or data it contains.

### Reconstruire

```sh
python -m climate_data.cities          # choisir les villes dans GeoNames
python -m climate_data.fetch_timeseries --country FR    # séries ERA5-Land (clé CDS requise), ou GB, DE, PT, LU, RS
python -m climate_data.build_cities --country FR
```

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
