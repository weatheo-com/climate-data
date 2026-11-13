# Municipality sources

The municipal climate datasets (FR, PT, LU, RS, DE, GB) take their list of municipalities, codes and reference points from the sources below. All files were retrieved on 2026-11-13 and are stored under `places/raw/<cc>/`; `scripts/fetch_places.sh` downloads them again.

## France (FR): 34,734 communes, INSEE code

- Source: "Liste des communes de France : code INSEE, codes postaux, EPCI, population, superficie" on data.gouv.fr
- URL: <https://www.data.gouv.fr/datasets/liste-des-communes-de-france-code-insee-codes-postaux-epci-population-superficie-62-indicateurs>
- Licence: Licence Ouverte 2.0 (Etalab)
- Files used: `communes-france-2026.csv` (<https://static.data.gouv.fr/resources/communes-et-villes-de-france-en-csv-excel-json-parquet-et-feather/20260617-155950/communes-france-2026.csv>)
- Scope: metropolitan France and Corsica; overseas departments not included.
- Retrieved: 2026-11-13

## Portugal (PT): 308 municípios, DICO code

- Source: Carta Administrativa Oficial de Portugal (CAOP) 2025, Direção-Geral do Território (DGT)
- URL: <https://www.dgterritorio.gov.pt/cartografia/cartografia-tematica/caop>
- Licence: CC BY
- Files used: `CAOP_Continente_2025-gpkg.zip`, `CAOP_RAA_2025-gpkg.zip`, `CAOP_RAM_2025-gpkg.zip` (from <https://geo2.dgterritorio.gov.pt/caop/>), municipality layers of the GeoPackages (mainland, Azores, Madeira). `municipios_caop2025_pointonsurface.csv` is derived from them: one point inside each municipality polygon (ST_PointOnSurface), in WGS84.
- Point used: the municipal seat from GeoNames `PT.txt` (<https://download.geonames.org/export/dump/PT.zip>, CC BY 4.0), put next to the CAOP file in `places/raw/pt/`: a seat feature (PPLC, PPLA, PPLA2) whose `admin2` is the DICO code, else the most populous populated place of that name in the municipality (304 of 308 matched); the CAOP interior point otherwise. Interior points can sit far up a mountain (Funchal: 667 m) while the town is near sea level.
- Retrieved: 2026-11-13

## Luxembourg (LU): 100 communes, LAU code

- Source: STATEC, "Codes LAU des communes du Grand-Duché de Luxembourg" on data.public.lu
- URL: <https://data.public.lu/fr/datasets/codes-lau-des-communes-du-grand-duche-de-luxembourg/>
- Licence: CC0
- Files used: `A1106.xlsx`, sheet "LU_SEP 2023" (<https://statistiques.public.lu/dam-assets/fr/donnees-autres-formats/territoire-environ-energie/territoire/A1106.xlsx>)
- Coordinates: GeoNames, <https://download.geonames.org/export/dump/>, licence CC BY 4.0; files `LU.zip` (`LU.txt`, ADM2 features) and `admin2Codes.txt`
- Retrieved: 2026-11-13

## Serbia (RS): 169 municipalities and cities (opštine i gradovi), RZS code

- Source: Republički zavod za statistiku (RZS), "Opštine i gradovi" (SIFOPS) on data.gov.rs
- URL: <https://data.gov.rs/sr/datasets/opshtine-i-gradovi/>
- Licence: Serbian Open Data Licence (SODL), https://data.gov.rs/sr/terms/: reuse for commercial and non-commercial purposes, free of charge, if each reuse names the publishing body (RZS), the download date (2026-11-13), the address and the changes made (here: coordinates from GeoNames and climate values added)
- Files used: `opshtine_sifops.csv` (<https://opendata.stat.gov.rs/data/WcfJsonRestService.Service1.svc/dataset/SIFOPS/1/csv>)
- Coordinates: GeoNames, <https://download.geonames.org/export/dump/>, licence CC BY 4.0; file `RS.zip` (`RS.txt`, ADM3 features)
- Retrieved: 2026-11-13

## Germany (DE): 10,949 Gemeinden, AGS code

- Source: Bundesamt für Kartographie und Geodäsie (BKG), Verwaltungsgebiete 1:250 000 mit Einwohnerzahlen (VG250-EW), Gemeinden with their reference points and population
- URL: <https://gdz.bkg.bund.de/> (product VG250-EW)
- Licence: Datenlizenz Deutschland Namensnennung 2.0 (dl-de/by-2-0), <https://www.govdata.de/dl-de/by-2-0>
- Attribution: (c) GeoBasis-DE / BKG (2026) dl-de/by-2-0, Daten veraendert
- Files used: `de_gemeinden_vg250ew.csv` (columns ags, ars, name, bez, land, lat, lon, pop, area_km2), merged from the VG250-EW Gemeinden layer and its points
- Codes: `code` = 8-digit AGS (leading zeros kept), `admin1_code` = Land (first 2 digits), `admin2_code` = Kreis (first 5 digits)
- Retrieved: 2026-11-13

## United Kingdom (GB): 8,545 built-up areas, BUA22CD code

- Source: Office for National Statistics (ONS), Built-up areas (December 2022), names, codes and centroids, from the ONS Open Geography Portal
- URL: <https://geoportal.statistics.gov.uk/>
- Licence: Open Government Licence v3.0, <https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/>
- Attribution: Source: Office for National Statistics licensed under the Open Government Licence v.3.0. Contains OS data (c) Crown copyright and database right 2022
- Files used: `bua2022.csv` (BUA22CD, BUA22NM, LONG, LAT, BNG_E, BNG_N)
- Codes: `admin1` from the code prefix: E = England (E92000001), W = Wales (W92000004), S = Scotland (S92000003), K = cross-border England and Wales (K04000001); no `admin2`
- Scope: England, Wales and Scotland; Northern Ireland is not covered by ONS built-up areas
- Retrieved: 2026-11-13

## Climate data

All climate values come from Copernicus ERA5-Land monthly means (0.1°), with ERA5 monthly means (0.25°) where ERA5-Land has no cell. Required attribution:

> Contains modified Copernicus Climate Change Service information 2026. Neither the European Commission nor ECMWF is responsible for any use that may be made of the Copernicus information or data it contains.
>
> Copernicus DEM GLO-90 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA.
