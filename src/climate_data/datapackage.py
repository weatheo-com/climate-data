"""Frictionless datapackage.json for one country's datasets."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ATTRIBUTION = (
    "Contains modified Copernicus Climate Change Service information 2026. Neither the European "
    "Commission nor ECMWF is responsible for any use that may be made of the Copernicus "
    "information or data it contains."
)
LICENSE = {"name": "CC-BY-4.0", "path": "https://creativecommons.org/licenses/by/4.0/",
           "title": "Creative Commons Attribution 4.0"}
HOMEPAGE = "https://weatheo.com/en/open-data"
SOURCES = [
    {"title": "Copernicus C3S ERA5-Land monthly averaged data from 1950 to present",
     "path": "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land-monthly-means"},
    {"title": "Copernicus C3S ERA5 monthly averaged data on single levels from 1940 to present",
     "path": "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels-monthly-means"},
    {"title": "ERA5-Land orography (geopotential, 0.1 deg), ECMWF",
     "path": "https://confluence.ecmwf.int/display/CKB/ERA5-Land%3A+data+documentation"},
    {"title": "Copernicus DEM GLO-90 (place elevations), © DLR e.V. 2010-2014 and © Airbus Defence and "
              "Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA",
     "path": "https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM"},
]
DAILY_SOURCES = [
    {"title": "Copernicus C3S ERA5-Land post-processed daily statistics from 1950 to present",
     "path": "https://cds.climate.copernicus.eu/datasets/derived-era5-land-daily-statistics"},
    {"title": "Copernicus C3S ERA5 post-processed daily statistics on single levels from 1940 to present",
     "path": "https://cds.climate.copernicus.eu/datasets/derived-era5-single-levels-daily-statistics"},
]
GEONAMES = {"title": "GeoNames gazetteer (coordinates), licence CC BY 4.0",
            "path": "https://download.geonames.org/export/dump/"}
PLACE_SOURCES = {
    "FR": [{"title": "Liste des communes de France (data.gouv.fr), licence Licence Ouverte 2.0",
            "path": "https://www.data.gouv.fr/datasets/liste-des-communes-de-france-code-insee-codes-postaux-epci-population-superficie-62-indicateurs"}],
    "PT": [{"title": "CAOP 2025, Direção-Geral do Território, licence CC BY",
            "path": "https://www.dgterritorio.gov.pt/cartografia/cartografia-tematica/caop"},
           {"title": "GeoNames gazetteer (municipal seat coordinates), licence CC BY 4.0",
            "path": "https://download.geonames.org/export/dump/"}],
    "LU": [{"title": "STATEC, Codes LAU des communes du Grand-Duché de Luxembourg (data.public.lu), licence CC0",
            "path": "https://data.public.lu/fr/datasets/codes-lau-des-communes-du-grand-duche-de-luxembourg/"},
           GEONAMES],
    "RS": [{"title": "RZS, Opštine i gradovi (data.gov.rs), downloaded 2026-11-13, Serbian Open Data Licence (SODL); modified: coordinates and climate values added",
            "path": "https://data.gov.rs/sr/datasets/opshtine-i-gradovi/"},
           GEONAMES],
    "DE": [{"title": "(c) GeoBasis-DE / BKG (2026), Verwaltungsgebiete 1:250 000 mit Einwohnerzahlen "
                     "(VG250-EW), licence dl-de/by-2-0 (Datenlizenz Deutschland Namensnennung 2.0); "
                     "Daten verändert: Klimawerte hinzugefügt",
            "path": "https://gdz.bkg.bund.de/index.php/default/verwaltungsgebiete-1-250-000-mit-einwohnerzahlen-ebenen-stand-31-12-vg250-ew-ebenen-31-12.html"}],
    "GB": [{"title": "Source: Office for National Statistics licensed under the Open Government Licence v.3.0. "
                     "Contains OS data (c) Crown copyright and database right 2022 (Built-up areas, December 2022)",
            "path": "https://geoportal.statistics.gov.uk/"}],
}
LIMITS = (
    "Values are reanalysis grid-cell values adjusted for altitude, not station observations: they "
    "can differ from official station normals, mostly near coasts, in cities and in steep terrain."
)
METHOD = (
    "Temperatures are moved from the grid cell's model elevation (grid_elevation_m) to the "
    "elevation of the municipality's reference point (elevation_m, Copernicus DEM GLO-90) with a "
    "fixed lapse rate of 6.5 degC per km: t = t_cell + 0.0065 * (grid_elevation_m - elevation_m). "
    "Precipitation is not adjusted. The 1961-1990 to 1991-2020 temperature shift does not depend "
    "on this adjustment."
)
CONTRIBUTORS = [{"title": "Weatheo (by CODELIO)", "path": "https://weatheo.com", "role": "publisher"}]

FIELD_DOC = {
    "country": "ISO 3166-1 alpha-2 country code",
    "code": "official municipality code (string, leading zeros kept)",
    "name": "municipality name",
    "admin1_code": "first-level administrative unit code",
    "admin1_name": "first-level administrative unit name",
    "admin2_code": "second-level administrative unit code (may be empty)",
    "admin2_name": "second-level administrative unit name (may be empty)",
    "latitude": "municipality reference point latitude (WGS84)",
    "longitude": "municipality reference point longitude (WGS84)",
    "grid_lat": "latitude of the reanalysis grid cell centre used",
    "grid_lon": "longitude of the reanalysis grid cell centre used",
    "grid_source": "era5-land (0.1 deg, primary) or era5 (0.25 deg, used where ERA5-Land has no cell)",
    "elevation_m": "elevation of the municipality reference point, m (Copernicus DEM GLO-90)",
    "grid_elevation_m": "model elevation of the grid cell used, m (reanalysis orography)",
    "month": "calendar month 1-12 (dataset B also 'annual')",
    "tmean_c": "mean 2 m air temperature at elevation_m, degC",
    "precip_mm": "mean monthly total precipitation, mm",
    "tmin_c": "mean daily minimum 2 m temperature at elevation_m, degC",
    "tmax_c": "mean daily maximum 2 m temperature at elevation_m, degC",
    "frost_days": "mean number of days with daily minimum below 0 degC (cell elevation, not adjusted)",
    "summer_days": "mean number of days with daily maximum at or above 25 degC (cell elevation, not adjusted)",
    "period": "reference period of the normals",
    "weatheo_url": "Weatheo forecast page of the municipality (empty when not matched)",
}


def _doc(col: str) -> str:
    if col in FIELD_DOC:
        return FIELD_DOC[col]
    for var, label in (("tmean", "mean temperature, degC"), ("tmax", "mean daily maximum, degC"),
                       ("tmin", "mean daily minimum, degC"), ("precip", "precipitation, mm"),
                       ("frost_days", "frost days"), ("summer_days", "summer days")):
        if col.startswith(var):
            if "shift_pct" in col:
                return f"relative change 1991-2020 vs 1961-1990 of {label.split(',')[0]}, percent"
            if "shift" in col:
                return f"change 1991-2020 minus 1961-1990 of {label}"
            period = "1961-1990" if "1961_1990" in col else "1991-2020"
            return f"{period} normal: {label}"
    return ""


def _type(s: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(s):
        return "boolean"
    if pd.api.types.is_integer_dtype(s):
        return "integer"
    if pd.api.types.is_float_dtype(s):
        return "number"
    return "string"


def schema(df: pd.DataFrame) -> dict:
    fields = []
    for c in df.columns:
        f = {"name": c, "type": _type(df[c])}
        d = _doc(c)
        if d:
            f["description"] = d
        fields.append(f)
    return {"fields": fields, "missingValues": [""]}


def build_package(country, tables: dict[str, pd.DataFrame], daily: bool,
                  n_places: int, n_loaded: int) -> dict:
    cc = country.code
    boxes = "; ".join(f"{b.name} (N {b.bbox[0]}, W {b.bbox[1]}, S {b.bbox[2]}, E {b.bbox[3]})"
                      for b in country.boxes)
    desc = (
        f"Climate normals 1991-2020 and their shift since 1961-1990 for {n_places} municipalities of "
        f"{country.name} ({country.code_label}), from Copernicus ERA5-Land monthly means (0.1 deg) "
        f"with ERA5 single-level monthly means (0.25 deg) where ERA5-Land has no cell. Each "
        f"municipality takes the nearest grid cell to its reference point. " + METHOD +
        f" Area covered: {boxes}."
    )
    if country.excluded:
        desc += " Excluded: " + country.excluded
    if n_loaded != n_places:
        desc += f" {n_loaded - n_places} loaded places fell outside the covered area and are not included."
    if daily:
        desc += " Daily statistics (tmin, tmax, frost and summer days) come from the C3S post-processed daily statistics (UTC days)."
    desc += " " + LIMITS + " " + ATTRIBUTION

    resources = []
    for name, df in tables.items():
        sch = schema(df)
        kind = "normals" if "normals" in name else "shift"
        title = (f"{country.name}: monthly climate normals 1991-2020 per municipality" if kind == "normals"
                 else f"{country.name}: climate shift 1961-1990 vs 1991-2020 per municipality")
        common = {"title": title, "licenses": [LICENSE], "schema": sch}
        resources.append({"name": name, "path": f"{name}.csv", "format": "csv",
                          "mediatype": "text/csv", "encoding": "utf-8", "profile": "tabular-data-resource",
                          "dialect": {"delimiter": ","}, **common})
        resources.append({"name": f"{name}_parquet", "path": f"{name}.parquet", "format": "parquet",
                          "mediatype": "application/vnd.apache.parquet", **common})
    return {
        "profile": "tabular-data-package",
        "name": f"weatheo-climate-{cc.lower()}",
        "title": f"{country.name} municipal climate normals 1991-2020 and climate shift since 1961-1990 (ERA5-Land)",
        "description": desc,
        "version": "1.0.0",
        "licenses": [LICENSE],
        "homepage": HOMEPAGE,
        "sources": SOURCES + (DAILY_SOURCES if daily else []) + PLACE_SOURCES.get(cc, []),
        "contributors": CONTRIBUTORS,
        "keywords": ["climate", "climate normals", "climate change", "ERA5-Land", "Copernicus", country.name],
        "spatial": country.code,
        "temporal": {"start": "1961-01", "end": "2020-12"},
        "resources": resources,
    }


def write(out_dir: Path, package: dict) -> Path:
    p = Path(out_dir) / "datapackage.json"
    p.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


# --- City datasets (daily weather, monthly climate, normals, annual indicators) ---

TIMESERIES_SOURCES = [
    {"title": "Copernicus C3S ERA5-Land hourly time series from 1950 to present (reanalysis-era5-land-timeseries)",
     "path": "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land-timeseries"},
    SOURCES[2],
    SOURCES[3],
    {"title": "GeoNames gazetteer cities5000 (city list, coordinates, population, time zone), licence CC BY 4.0",
     "path": "https://download.geonames.org/export/dump/"},
]
CITY_METHOD = (
    "Each city takes the ERA5-Land time series (0.1 deg) of the grid cell at its GeoNames point, or of a "
    "neighbouring land cell when that cell is sea. Hourly values are grouped into local civil days (the "
    "city's IANA time zone); only complete days are kept. Temperatures are adjusted from the cell "
    "elevation to the city elevation with 6.5 degC per km. Wind is the mean of hourly 10 m wind speeds, "
    "not gusts. Monthly and annual values use complete months and years only."
)
CITY_FIELD_DOC = {
    "country": "ISO 3166-1 alpha-2 country code",
    "city_id": "GeoNames id of the city",
    "name": "city name (GeoNames)",
    "ascii_name": "city name in ASCII (GeoNames)",
    "admin1_code": "GeoNames first-level administrative division code",
    "admin1_name": "first-level administrative division name",
    "latitude": "city latitude, decimal degrees (WGS84, GeoNames)",
    "longitude": "city longitude, decimal degrees (WGS84, GeoNames)",
    "population": "population (GeoNames)",
    "timezone": "IANA time zone used for local days",
    "rank": "rank by population within the country (1 = largest)",
    "grid_lat": "latitude of the ERA5-Land cell centre, decimal degrees",
    "grid_lon": "longitude of the ERA5-Land cell centre, decimal degrees",
    "elevation_m": "city elevation, m (Copernicus DEM GLO-90)",
    "grid_elevation_m": "ERA5-Land model elevation of the cell, m",
    "weatheo_url": "Weatheo forecast page of the city (empty when not matched)",
    "tmean_annual_c": "mean annual temperature 1991-2020, degC",
    "precip_annual_mm": "mean annual precipitation 1991-2020, mm",
    "trend_c_per_decade_1951_2025": "linear trend of annual mean temperature 1951-2025, degC per decade",
    "trend_c_per_decade_1981_2025": "linear trend of annual mean temperature 1981-2025, degC per decade",
    "warmest_year": "warmest year 1951-2025 (annual mean temperature)",
    "coldest_year": "coldest year 1951-2025 (annual mean temperature)",
    "wettest_year": "wettest year 1951-2025 (annual precipitation)",
    "driest_year": "driest year 1951-2025 (annual precipitation)",
    "date": "local calendar date",
    "year": "calendar year",
    "month": "month (1-12)",
    "tmean_c": "mean temperature, degC",
    "tmin_c": "minimum temperature, degC",
    "tmax_c": "maximum temperature, degC",
    "precip_mm": "precipitation, mm",
    "wind_mean_kmh": "mean 10 m wind speed, km/h",
    "wind_max_kmh": "highest hourly 10 m wind speed (not gusts), km/h",
    "solar_kwh_m2": "surface solar radiation downwards, kWh/m2",
    "solar_kwh_m2_day": "surface solar radiation downwards per day, kWh/m2",
    "tmin_mean_c": "mean daily minimum temperature, degC",
    "tmax_mean_c": "mean daily maximum temperature, degC",
    "tmin_abs_c": "lowest daily minimum temperature, degC",
    "tmax_abs_c": "highest daily maximum temperature, degC",
    "tmean_anomaly_c": "mean temperature minus the 1991-2020 mean, degC",
    "precip_anomaly_pct": "precipitation relative to the 1991-2020 mean, percent",
    "max_1day_precip_mm": "highest daily precipitation, mm",
    "wet_days": "days with precipitation >= 1 mm",
    "heavy_rain_days": "days with precipitation >= 20 mm",
    "frost_days": "days with tmin < 0 degC",
    "ice_days": "days with tmax < 0 degC",
    "summer_days": "days with tmax >= 25 degC",
    "hot_days": "days with tmax >= 30 degC",
    "tropical_nights": "days with tmin >= 20 degC",
    "hdd_15_5": "heating degree days, base 15.5 degC, degC day",
    "hdd_18": "heating degree days, base 18 degC, degC day",
    "cdd_18": "cooling degree days, base 18 degC, degC day",
    "cdd_22": "cooling degree days, base 22 degC, degC day",
    "gtz_20_15": "Gradtagzahl 20/15 (VDI 3807), degC day",
    "rank_warmest": "rank of the year by annual mean temperature (1 = warmest)",
}


def city_schema(df: pd.DataFrame, daily: bool = False) -> dict:
    fields = []
    for c in df.columns:
        t = "date" if c == "date" else _type(df[c])
        if c in ("warmest_year", "coldest_year", "wettest_year", "driest_year", "year", "month"):
            t = "integer"
        f = {"name": c, "type": t}
        d = CITY_FIELD_DOC.get(c, "")
        if d and daily and c.startswith(("tmean", "tmin", "tmax", "precip", "solar", "wind")):
            d = "daily " + d
        if d:
            f["description"] = d
        fields.append(f)
    return {"fields": fields, "missingValues": [""]}


def build_city_package(cc: str, country_name: str, tables: dict[str, pd.DataFrame],
                       names: dict[str, str], n_cities: int) -> dict:
    """Datapackage for the city files. tables keys: cities, daily, daily_csv, monthly, normals, annual;
    names: the file names from build_cities.file_names()."""
    desc = (
        f"Daily weather 1950-2025, monthly climate, climate normals 1991-2020 and annual climate indicators "
        f"1951-2025 for the {n_cities} largest cities of {country_name}, from the Copernicus ERA5-Land "
        f"hourly time series. " + CITY_METHOD + " " + LIMITS + " " + ATTRIBUTION
    )
    csv = {"format": "csv", "mediatype": "text/csv", "encoding": "utf-8", "profile": "tabular-data-resource",
           "dialect": {"delimiter": ","}}
    parquet = {"format": "parquet", "mediatype": "application/vnd.apache.parquet"}
    specs = [
        ("cities", names["cities"], csv, f"{country_name}: cities with grid cell, elevation and climate summary", "cities", False),
        ("daily", names["daily_parquet"], parquet, f"{country_name}: daily weather 1950-2025 per city", "daily", True),
        ("daily_csv", names["daily_zip"], {"format": "zip", "mediatype": "application/zip"},
         f"{country_name}: daily weather 1950-2025, one CSV per city (<cc>_<city>_<city_id>_daily.csv)", "daily_csv", True),
        ("monthly", names["monthly_csv"], csv, f"{country_name}: monthly climate 1950-2025 per city", "monthly", False),
        ("monthly_parquet", names["monthly_parquet"], parquet, f"{country_name}: monthly climate 1950-2025 per city", "monthly", False),
        ("normals", names["normals"], csv, f"{country_name}: monthly climate normals 1991-2020 per city", "normals", False),
        ("annual", names["annual"], csv, f"{country_name}: annual climate indicators 1951-2025 per city", "annual", False),
    ]
    resources = []
    for key, path, fmt, title, table, is_daily in specs:
        resources.append({"name": f"{cc.lower()}_city_{key}", "path": path, **fmt, "title": title,
                          "licenses": [LICENSE], "schema": city_schema(tables[table], daily=is_daily)})
    return {
        "profile": "tabular-data-package",
        "name": f"weatheo-city-climate-{cc.lower()}",
        "title": f"{country_name} city daily weather 1950-2025 and climate indicators (ERA5-Land)",
        "description": desc,
        "version": "1.1.0",
        "licenses": [LICENSE],
        "homepage": HOMEPAGE,
        "sources": TIMESERIES_SOURCES,
        "contributors": CONTRIBUTORS,
        "keywords": ["climate", "weather history", "degree days", "climate normals", "ERA5-Land",
                     "Copernicus", country_name],
        "spatial": cc,
        "temporal": {"start": "1950-01-01", "end": "2025-12-31"},
        "resources": resources,
    }


def write_named(path: Path, package: dict) -> Path:
    p = Path(path)
    p.write_text(json.dumps(package, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return p
