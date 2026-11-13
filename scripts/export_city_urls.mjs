#!/usr/bin/env node
/**
 * Lists every live weatheo.com town page for FR, PT, LU, RS and writes
 * places/urls/<CC>.csv: country, code, name, admin1_name, latitude, longitude, path.
 *
 * Which pages are live: the site's own sitemaps (https://weatheo.com/sitemap.xml
 * and its children), the list the site publishes from its D1 `cities` table.
 * A town in no sitemap answers 404 (checked 2026-11-13: Baroville, Andert-et-Condon).
 * `path` is locale-less (/{country_slug}/{region_slug}/{city_slug}, cityPath()
 * in lib/seo/cityRoute.ts without the locale); the page is
 * https://weatheo.com/<locale><path>. Native locales, always served at any
 * population (data/seo/country-locales.json): FR fr, LU de+fr, PT pt, RS en.
 *
 * Names and coordinates for those paths come from the site's own builder:
 * scripts/build-cities.mjs is taken from the site repo (git show
 * origin/vite:...) into cache/site/ and run unchanged on the SimpleMaps Pro CSV;
 * its slugify() also keys the French commune list (code_insee, reg_nom,
 * nom_standard, latitude/longitude_centre), which carries most French pages and
 * gives the INSEE code. A live path found in neither keeps empty fields and is
 * counted in the summary.
 *
 * Usage: node scripts/export_city_urls.mjs [--site <weatheo.com checkout>]
 *        [--world <worldcities.csv>] [--fr <fr_rows.csv>] [--refresh]
 * The sitemap paths are cached in cache/site/sitemap-city-paths.txt; --refresh refetches.
 */
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const WORK = path.resolve(ROOT, '../../');
const arg = (name, def) => {
  const i = process.argv.indexOf(name);
  return i > 0 ? process.argv[i + 1] : def;
};
const SITE = arg('--site', path.join(WORK, 'weatheo.com'));
const WORLD = arg('--world', path.join(WORK, 'simplemaps_worldcities_prov1.91/worldcities.csv'));
const FR_ROWS = arg('--fr', path.join(WORK, 'weatheo data/used/FR/fr_rows (1).csv'));
const ORIGIN = 'https://weatheo.com';
const COUNTRIES = ['FR', 'PT', 'LU', 'RS'];
const SCRATCH = path.join(ROOT, 'cache/site');
const OUT = path.join(ROOT, 'places/urls');
mkdirSync(SCRATCH, { recursive: true });

// ---- 1. live town paths from the sitemaps -------------------------------
const pathsFile = path.join(SCRATCH, 'sitemap-city-paths.txt');
const want = new Set(COUNTRIES.map((c) => c.toLowerCase()));
let live;
if (existsSync(pathsFile) && !process.argv.includes('--refresh')) {
  live = readFileSync(pathsFile, 'utf8').split('\n').filter(Boolean);
} else {
  const locs = (xml) => [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1].trim());
  const get = async (u) => {
    const r = await fetch(u, { headers: { 'user-agent': 'climate-data-export' } });
    if (!r.ok) throw new Error(`${r.status} ${u}`);
    return r.text();
  };
  const set = new Set();
  for (const child of locs(await get(`${ORIGIN}/sitemap.xml`))) {
    if (!/cities/.test(child)) continue;
    for (const u of locs(await get(child))) {
      const parts = decodeURI(u.slice(ORIGIN.length)).split('/');
      // ['', locale, country, region, city] = a town page; longer = a sub-page
      if (parts.length === 5 && want.has(parts[2])) set.add(`/${parts.slice(2).join('/')}`);
    }
  }
  live = [...set].sort();
  writeFileSync(pathsFile, live.join('\n') + '\n');
}

// ---- 2. the site's own city builder, from origin/vite (read-only use) ----
const builder = path.join(SCRATCH, 'build-cities.mjs');
writeFileSync(builder, execFileSync('git', ['-C', SITE, 'show', 'origin/vite:scripts/build-cities.mjs']));
const citiesDir = path.join(SCRATCH, 'cities');
execFileSync('node', [builder, WORLD, citiesDir], { stdio: ['ignore', 'ignore', 'inherit'] });
const { slugify } = await import(builder);
const byPath = new Map(); // path -> {name, admin1, lat, lng}
for (const r of JSON.parse(readFileSync(path.join(citiesDir, 'cities.json'), 'utf8'))) {
  if (!want.has(r.country_slug)) continue;
  byPath.set(`/${r.country_slug}/${r.region_slug}/${r.city_slug}`,
    { name: r.city, admin1: r.admin_name, lat: r.lat, lng: r.lng });
}

// ---- 3. French communes: INSEE code, and data for paths the CSV lacks ----
function splitCsv(line) {
  const out = [];
  let cur = '';
  let q = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (q) {
      if (c === '"' && line[i + 1] === '"') { cur += '"'; i++; }
      else if (c === '"') q = false;
      else cur += c;
    } else if (c === '"') q = true;
    else if (c === ',') { out.push(cur); cur = ''; }
    else cur += c;
  }
  out.push(cur);
  return out;
}
const communeByPath = new Map(); // fr path -> [{code, name, admin1, lat, lng}]
if (existsSync(FR_ROWS)) {
  const lines = readFileSync(FR_ROWS, 'utf8').split(/\r?\n/).filter(Boolean);
  const H = Object.fromEntries(splitCsv(lines[0]).map((h, i) => [h, i]));
  for (const line of lines.slice(1)) {
    const c = splitCsv(line);
    let code = (c[H.code_insee] || '').trim();
    if (/^\d{1,4}$/.test(code)) code = code.padStart(5, '0'); // the file dropped leading zeros
    const lat = Number.parseFloat(c[H.latitude_centre] || c[H.latitude_mairie]);
    const lng = Number.parseFloat(c[H.longitude_centre] || c[H.longitude_mairie]);
    if (!code) continue;
    const p = `/fr/${slugify(c[H.reg_nom])}/${slugify(c[H.nom_standard])}`;
    if (!communeByPath.has(p)) communeByPath.set(p, []);
    communeByPath.get(p).push({ code, name: c[H.nom_standard], admin1: c[H.reg_nom],
      lat: Number.isFinite(lat) ? lat : null, lng: Number.isFinite(lng) ? lng : null });
  }
} else {
  console.warn('no French commune file, FR codes left empty:', FR_ROWS);
}

function km(a, b) {
  const rad = (d) => (d * Math.PI) / 180;
  const h = Math.sin(rad(b.lat - a.lat) / 2) ** 2
    + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(rad(b.lng - a.lng) / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}

/** The commune behind a French page: same path, the nearest one within 15 km
 *  when the page has coordinates, else the only one. */
function commune(p, place) {
  const list = communeByPath.get(p) ?? [];
  if (place) {
    let best = null;
    for (const c of list) {
      if (c.lat == null) continue;
      const d = km(place, c);
      if (d <= 15 && (!best || d < best.d)) best = { c, d };
    }
    return best?.c ?? null;
  }
  return list.length === 1 ? list[0] : null;
}

// ---- 4. write places/urls/<CC>.csv --------------------------------------
const esc = (v) => {
  const s = String(v ?? '');
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
};
mkdirSync(OUT, { recursive: true });
const summary = {};
for (const cc of COUNTRIES) {
  const lc = cc.toLowerCase();
  const lines = ['country,code,name,admin1_name,latitude,longitude,path'];
  const s = { pages: 0, withCode: 0, noCoords: 0 };
  for (const p of live.filter((x) => x.split('/')[1] === lc)) {
    const w = byPath.get(p);
    const place = w ? { lat: w.lat, lng: w.lng } : null;
    const c = cc === 'FR' ? commune(p, place) : null;
    const row = w ?? c ?? {};
    const lat = row.lat ?? c?.lat;
    const lng = row.lng ?? c?.lng;
    if (lat == null || lng == null) s.noCoords++;
    if (c) s.withCode++;
    s.pages++;
    lines.push([cc, c?.code ?? '', row.name ?? '', row.admin1 ?? '', lat ?? '', lng ?? '', p].map(esc).join(','));
  }
  writeFileSync(path.join(OUT, `${cc}.csv`), lines.join('\n') + '\n');
  summary[cc] = s;
}
console.log(JSON.stringify(summary));
