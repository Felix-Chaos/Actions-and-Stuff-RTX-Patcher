// Guardrail: every locale must carry the same key set as the fallback.
//
// Key drift degrades silently at runtime -- a missing key just falls back to
// English with a console warning nobody reads. This turns that into a failure.
//
// Usage: node scripts/check-locales.mjs
import { LOCALES, FALLBACK_LOCALE } from '../src/i18n/registry.js';

function flatten(obj, prefix = '', out = {}) {
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) flatten(v, key, out);
    else out[key] = v;
  }
  return out;
}

const dicts = new Map();
for (const { code, loader } of LOCALES) {
  dicts.set(code, flatten((await loader()).default));
}

const reference = Object.keys(dicts.get(FALLBACK_LOCALE)).sort();
let failed = false;

for (const [code, dict] of dicts) {
  if (code === FALLBACK_LOCALE) continue;
  const keys = new Set(Object.keys(dict));
  const missing = reference.filter(k => !keys.has(k));
  const extra = [...keys].filter(k => !reference.includes(k)).sort();

  if (missing.length) {
    failed = true;
    console.error(`\n[${code}] ${missing.length} key(s) missing vs ${FALLBACK_LOCALE}:`);
    for (const k of missing) console.error(`  - ${k}`);
  }
  if (extra.length) {
    failed = true;
    console.error(`\n[${code}] ${extra.length} key(s) not present in ${FALLBACK_LOCALE}:`);
    for (const k of extra) console.error(`  + ${k}`);
  }
}

// * Empty strings are almost always an unfinished translation, not a real value.
for (const [code, dict] of dicts) {
  const blank = Object.entries(dict).filter(([, v]) => typeof v !== 'string' || v.trim() === '');
  if (blank.length) {
    failed = true;
    console.error(`\n[${code}] ${blank.length} empty or non-string value(s):`);
    for (const [k] of blank) console.error(`  ! ${k}`);
  }
}

if (failed) process.exit(1);
console.log(`All ${dicts.size} locales match ${FALLBACK_LOCALE} (${reference.length} keys).`);
