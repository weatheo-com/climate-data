#!/usr/bin/env node
// Dependency-free. Usage:
//   node scripts/build.mjs <source-dir>   regenerate data/<dataset>/<dataset>.csv without OpenWeather columns
//   node scripts/build.mjs --check        verify data/ (no owm_/rain/sunshine/precip/sources_agree headers, row counts)
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const EXPECTED = { 'june-2026-heatwave': 56, 'past-12-months': 87, 'summer-2026-europe': 32, 'summer-2026-france': 25, 'winter-2025-26': 72 };
const KEEP_META = new Set(['city', 'country', 'latitude', 'longitude', 'days', 'forecast_page']);
const keep = (h) => KEEP_META.has(h) || h.startsWith('era5_');

// RFC 4180 parser: quoted fields, doubled quotes, embedded commas/newlines, CRLF or LF.
function parse(text) {
  const rows = [];
  let row = [], field = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"') { if (text[i + 1] === '"') { field += '"'; i++; } else q = false; }
      else field += c;
    } else if (c === '"') q = true;
    else if (c === ',') { row.push(field); field = ''; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(field); field = ''; rows.push(row); row = [];
    } else field += c;
  }
  if (field !== '' || row.length) { row.push(field); rows.push(row); }
  return rows;
}
const esc = (v) => (/[",\n\r]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
const serialize = (rows) => rows.map((r) => r.map(esc).join(',')).join('\n') + '\n';

const arg = process.argv[2];
if (!arg) { console.error('usage: build.mjs <source-dir> | --check'); process.exit(2); }

if (arg === '--check') {
  let bad = 0;
  for (const [id, n] of Object.entries(EXPECTED)) {
    const file = path.join(ROOT, 'data', id, `${id}.csv`);
    if (!existsSync(file)) { console.error(`missing ${file}`); bad++; continue; }
    const rows = parse(readFileSync(file, 'utf8'));
    for (const h of rows[0]) {
      if (/^owm_|rain|sunshine|precip|sources_agree/i.test(h)) { console.error(`${id}: forbidden column ${h}`); bad++; }
    }
    if (rows.length - 1 !== n) { console.error(`${id}: ${rows.length - 1} rows, expected ${n}`); bad++; }
    if (rows.some((r) => r.length !== rows[0].length)) { console.error(`${id}: ragged rows`); bad++; }
  }
  console.log(bad ? `check FAILED (${bad})` : 'check OK');
  process.exit(bad ? 1 : 0);
}

for (const id of Object.keys(EXPECTED)) {
  const rows = parse(readFileSync(path.join(arg, `${id}.csv`), 'utf8'));
  const idx = rows[0].map((h, i) => (keep(h) ? i : -1)).filter((i) => i >= 0);
  const dropped = rows[0].filter((h) => !keep(h));
  const odd = dropped.filter((h) => !h.startsWith('owm_') && h !== 'sources_agree_within_1c');
  if (odd.length) console.warn(`${id}: dropped unrecognised columns: ${odd.join(', ')}`);
  const out = rows.map((r) => idx.map((i) => r[i]));
  mkdirSync(path.join(ROOT, 'data', id), { recursive: true });
  writeFileSync(path.join(ROOT, 'data', id, `${id}.csv`), serialize(out));
  console.log(`${id}: ${out.length - 1} rows, ${idx.length} columns`);
}
