// Locale files are nested for readability; lookups are flat dot-paths.
// Shared by the runtime and scripts/check-locales.mjs so both agree on what a key is.
export function flatten(obj, prefix = '', out = {}) {
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) flatten(v, key, out);
    else out[key] = v;
  }
  return out;
}
