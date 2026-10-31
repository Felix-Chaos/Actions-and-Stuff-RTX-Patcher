// Guardrail: every locale must carry the same key set as the fallback.
//
// Key drift degrades silently at runtime -- a missing key just falls back to
// English with a console warning nobody reads. This turns that into a failure.
//
// Checks, per bundle (see BUNDLES in src/i18n/registry.js):
//   - every locale has exactly the fallback's keys, none empty;
//   - no key lives in more than one bundle (they share one key space);
//   - every literal key used in src/main.js and in the Rust log calls exists.
//
// Usage: node scripts/check-locales.mjs
import { readFile, readdir } from 'node:fs/promises';
import { LOCALES, FALLBACK_LOCALE, BUNDLES } from '../src/i18n/registry.js';
import { flatten } from '../src/i18n/flatten.js';

let failed = false;
const fail = (title, items, mark) => {
  failed = true;
  console.error(`\n${title}`);
  for (const i of items) console.error(`  ${mark} ${i}`);
};

const readJson = async (rel) =>
  flatten(JSON.parse(await readFile(new URL(`../src/i18n/${rel}`, import.meta.url), 'utf8')));

const allFallbackKeys = new Map(); // key -> bundle name
let total = 0;

for (const bundle of BUNDLES) {
  const dicts = new Map();
  for (const { code } of LOCALES) {
    dicts.set(code, await readJson(bundle.path(code)));
  }

  const reference = Object.keys(dicts.get(FALLBACK_LOCALE)).sort();
  total += reference.length;

  for (const [code, dict] of dicts) {
    if (code === FALLBACK_LOCALE) continue;
    const keys = new Set(Object.keys(dict));
    const refSet = new Set(reference);
    const missing = reference.filter(k => !keys.has(k));
    const extra = [...keys].filter(k => !refSet.has(k)).sort();
    const partial = LOCALES.find(l => l.code === code).partialBundles?.includes(bundle.name);
    if (missing.length && !partial) fail(`[${bundle.name}/${code}] ${missing.length} key(s) missing vs ${FALLBACK_LOCALE}:`, missing, '-');
    if (extra.length) fail(`[${bundle.name}/${code}] ${extra.length} key(s) not present in ${FALLBACK_LOCALE}:`, extra, '+');
  }

  // * Empty strings are almost always an unfinished translation, not a real value.
  for (const [code, dict] of dicts) {
    const blank = Object.entries(dict).filter(([, v]) => typeof v !== 'string' || v.trim() === '').map(([k]) => k);
    if (blank.length) fail(`[${bundle.name}/${code}] ${blank.length} empty or non-string value(s):`, blank, '!');
  }

  // ! A renamed or dropped {placeholder} silently prints the raw "{name}".
  const vars = s => [...String(s).matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort().join(',');
  const ref = dicts.get(FALLBACK_LOCALE);
  for (const [code, dict] of dicts) {
    if (code === FALLBACK_LOCALE) continue;
    const off = Object.keys(dict).filter(k => k in ref && vars(dict[k]) !== vars(ref[k]));
    if (off.length) fail(`[${bundle.name}/${code}] ${off.length} value(s) with placeholders differing from ${FALLBACK_LOCALE}:`, off, '~');
  }

  const dupes = [];
  for (const k of reference) {
    if (allFallbackKeys.has(k)) dupes.push(`${k} (${allFallbackKeys.get(k)} and ${bundle.name})`);
    else allFallbackKeys.set(k, bundle.name);
  }
  if (dupes.length) fail(`${dupes.length} key(s) defined in more than one bundle:`, dupes, '!');
}

// Languages Crowdin exports before they are offered in the registry may be
// partial (missing keys fall back to English), but must never carry a key their
// English bundle lacks, e.g. a key left behind in the wrong bundle by a move.
const registered = new Set(LOCALES.map(l => l.code));
for (const bundle of BUNDLES) {
  const enKeys = new Set(Object.keys(await readJson(bundle.path(FALLBACK_LOCALE))));
  const dirRel = bundle.path('x').replace(/x\.json$/, '');
  const dirUrl = new URL(`../src/i18n/${dirRel}`, import.meta.url);
  for (const file of (await readdir(dirUrl)).filter(f => f.endsWith('.json'))) {
    const code = file.slice(0, -5);
    if (registered.has(code)) continue;
    const stray = Object.keys(await readJson(`${dirRel}${file}`)).filter(k => !enKeys.has(k));
    if (stray.length) fail(`[${bundle.name}/${code}] ${stray.length} key(s) not present in ${FALLBACK_LOCALE}:`, stray, '+');
  }
}

// Literal keys at the call sites. Plural helpers resolve to <key>.one/.other.
const exists = (key, plural) =>
  plural ? allFallbackKeys.has(`${key}.one`) && allFallbackKeys.has(`${key}.other`) : allFallbackKeys.has(key);

const unknown = [];
const mainJs = await readFile(new URL('../src/main.js', import.meta.url), 'utf8');
for (const m of mainJs.matchAll(/\b(t|tEn|msg|tPlural|msgPlural)\(\s*['"`]([\w.]+)['"`]/g)) {
  if (!exists(m[2], m[1].endsWith('Plural'))) unknown.push(`src/main.js: ${m[2]}`);
}
const rustDir = new URL('../src-tauri/src/', import.meta.url);
for (const file of (await readdir(rustDir)).filter(f => f.endsWith('.rs'))) {
  const src = await readFile(new URL(file, rustDir), 'utf8');
  for (const m of src.matchAll(/"(log\.backend\.[\w.]+)"/g)) {
    if (!exists(m[1], false)) unknown.push(`src-tauri/src/${file}: ${m[1]}`);
  }
}
const unknownKeys = [...new Set(unknown)];
if (unknownKeys.length) fail(`${unknownKeys.length} key(s) used in code but missing from ${FALLBACK_LOCALE}:`, unknownKeys, '?');

if (failed) process.exit(1);
console.log(`All ${LOCALES.length} locales match ${FALLBACK_LOCALE} across ${BUNDLES.length} bundles (${total} keys); every key used in code exists.`);
