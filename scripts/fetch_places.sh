#!/usr/bin/env bash
# Download the raw municipality files into places/raw/<cc>/ (sources: docs/places-sources.md).
# Usage: scripts/fetch_places.sh [fr] [pt] [lu] [rs]   (no argument = all four)
# Needs curl and unzip; PT also needs ogr2ogr (GDAL) to turn the CAOP polygons into points.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RAW="$ROOT/places/raw"
GEONAMES="https://download.geonames.org/export/dump"

get() { # url dest
  echo "  $1"
  curl -fsSL --retry 3 -o "$2.part" "$1" && mv "$2.part" "$2"
}

fetch_fr() {
  local d="$RAW/fr"; mkdir -p "$d"
  # data.gouv.fr "Liste des communes de France" (Licence Ouverte 2.0), 2026 edition
  get "https://static.data.gouv.fr/resources/communes-et-villes-de-france-en-csv-excel-json-parquet-et-feather/20260617-155950/communes-france-2026.csv" \
    "$d/communes-france-2026.csv"
}

fetch_pt() {
  local d="$RAW/pt"; mkdir -p "$d/cont" "$d/raa" "$d/ram"
  # DGT CAOP 2025 (CC BY): mainland, Azores, Madeira
  get "https://geo2.dgterritorio.gov.pt/caop/CAOP_Continente_2025-gpkg.zip" "$d/CAOP_Continente_2025-gpkg.zip"
  get "https://geo2.dgterritorio.gov.pt/caop/CAOP_RAA_2025-gpkg.zip" "$d/CAOP_RAA_2025-gpkg.zip"
  get "https://geo2.dgterritorio.gov.pt/caop/CAOP_RAM_2025-gpkg.zip" "$d/CAOP_RAM_2025-gpkg.zip"
  unzip -oq "$d/CAOP_Continente_2025-gpkg.zip" -d "$d/cont"
  unzip -oq "$d/CAOP_RAA_2025-gpkg.zip" -d "$d/raa"
  unzip -oq "$d/CAOP_RAM_2025-gpkg.zip" -d "$d/ram"

  # One point inside each municipality polygon (ST_PointOnSurface), WGS84 lon/lat in X/Y.
  local out="$d/municipios_caop2025_pointonsurface.csv" tmp
  tmp="$(mktemp -d)"
  local i=0 gpkg layer
  for pair in \
    "cont/Continente_CAOP2025.gpkg:cont_municipios" \
    "raa/ArqAcores_GCentral_GOriental_CAOP2025.gpkg:raa_cen_ori_municipios" \
    "raa/ArqAcores_GOcidental_CAOP2025.gpkg:raa_oci_municipios" \
    "ram/ArqMadeira_CAOP2025.gpkg:ram_municipios"; do
    gpkg="${pair%%:*}"; layer="${pair##*:}"; i=$((i + 1))
    ogr2ogr -f CSV "$tmp/$i.csv" "$d/$gpkg" -t_srs EPSG:4326 -dialect SQLite \
      -sql "SELECT ST_PointOnSurface(geom) AS geom, dtmn, municipio, distrito_ilha, nuts3_cod, nuts3, nuts2, nuts1, area_ha FROM $layer" \
      -lco GEOMETRY=AS_XY -lco STRING_QUOTING=IF_AMBIGUOUS
  done
  head -n 1 "$tmp/1.csv" > "$out"
  for f in "$tmp"/*.csv; do tail -n +2 "$f" >> "$out"; done
  rm -rf "$tmp"
}

fetch_lu() {
  local d="$RAW/lu"; mkdir -p "$d"
  # STATEC LAU codes on data.public.lu (CC0)
  get "https://statistiques.public.lu/dam-assets/fr/donnees-autres-formats/territoire-environ-energie/territoire/A1106.xlsx" "$d/A1106.xlsx"
  # GeoNames (CC BY 4.0)
  get "$GEONAMES/LU.zip" "$d/LU.zip"
  get "$GEONAMES/admin2Codes.txt" "$d/admin2Codes.txt"
  unzip -oq "$d/LU.zip" -d "$d"
}

fetch_rs() {
  local d="$RAW/rs"; mkdir -p "$d"
  # RZS "Opštine i gradovi" (SIFOPS) on data.gov.rs (licence sodl)
  get "https://opendata.stat.gov.rs/data/WcfJsonRestService.Service1.svc/dataset/SIFOPS/1/csv" "$d/opshtine_sifops.csv"
  # GeoNames (CC BY 4.0)
  get "$GEONAMES/RS.zip" "$d/RS.zip"
  unzip -oq "$d/RS.zip" -d "$d"
}

countries=("$@")
[ ${#countries[@]} -eq 0 ] && countries=(fr pt lu rs)
for cc in "${countries[@]}"; do
  case "$cc" in
    fr|pt|lu|rs) echo "[$cc]"; "fetch_$cc" ;;
    *) echo "unknown country: $cc (fr, pt, lu, rs)" >&2; exit 2 ;;
  esac
done
echo "done: $RAW"
