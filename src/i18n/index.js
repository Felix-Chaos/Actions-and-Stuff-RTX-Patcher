// Minimal i18n engine for the patcher.
//
// The frontend is served unbundled (tauri.conf.json -> frontendDist: "../src"),
// so locales are plain ES modules rather than JSON: no bundler, no import
// attributes, no CSP change, and every string stays readable in a diff.
//
// * Log and console OUTPUT is never translated. See .agents/I18N.md for the rule.
import { LOCALES, FALLBACK_LOCALE } from './registry.js';

let current = FALLBACK_LOCALE;
let dict = {};
let fallbackDict = {};
const listeners = new Set();

// Locale files are nested for readability; lookups are flat dot-paths.
function flatten(obj, prefix = '', out = {}) {
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === 'object' && !Array.isArray(v)) flatten(v, key, out);
    else out[key] = v;
  }
  return out;
}

async function loadDict(code) {
  const entry = LOCALES.find(l => l.code === code)
    ?? LOCALES.find(l => l.code === FALLBACK_LOCALE);
  const mod = await entry.loader();
  return flatten(mod.default);
}

/** Load the fallback plus the requested locale and translate the document once. */
export async function initI18n(initialLocale) {
  fallbackDict = await loadDict(FALLBACK_LOCALE);
  current = LOCALES.some(l => l.code === initialLocale) ? initialLocale : FALLBACK_LOCALE;
  dict = current === FALLBACK_LOCALE ? fallbackDict : await loadDict(current);
  document.documentElement.lang = current;
  applyTranslations(document);
}

/** Translate `key`, replacing every {name} placeholder from `vars`. */
export function t(key, vars) {
  let str = dict[key] ?? fallbackDict[key];
  if (str === undefined) {
    // ! A missing key means the locale file and the call site drifted apart.
    console.warn(`[i18n] missing key: ${key}`);
    return key;
  }
  if (vars) {
    for (const [k, v] of Object.entries(vars)) str = str.replaceAll(`{${k}}`, String(v));
  }
  return str;
}

/**
 * Singular/plural variant of `t`: resolves `<key>.one` or `<key>.other` and
 * pre-fills {count}. English and German both split only on n === 1 here, so
 * full CLDR plural rules would be dead weight.
 */
export function tPlural(key, n, vars = {}) {
  return t(`${key}.${n === 1 ? 'one' : 'other'}`, { count: n, ...vars });
}

/** Currently active language code. */
export function getLocale() {
  return current;
}

/** Every selectable language, for building the dropdowns. */
export function getLocales() {
  return LOCALES.map(({ code, label }) => ({ code, label }));
}

/** Switch language and re-translate the document in place. */
export async function setLocale(code) {
  if (code === current) return;
  dict = code === FALLBACK_LOCALE ? fallbackDict : await loadDict(code);
  current = code;
  document.documentElement.lang = current;
  applyTranslations(document);
  for (const fn of listeners) fn(code);
}

/**
 * Register a callback for language changes, for text that applyTranslations
 * cannot reach (anything rendered from JS rather than annotated in the HTML).
 * Returns an unsubscribe function.
 */
export function onLocaleChange(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

/**
 * Swap every annotated element under `root` to the active language.
 *
 * ! data-i18n overwrites textContent, so it belongs only on elements whose
 * ! children are pure text. On a parent with element children it deletes them
 * ! silently -- put it on the inner <span>, never on the wrapping <button>.
 */
export function applyTranslations(root = document) {
  root.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.getAttribute('data-i18n'));
  });
  root.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    el.setAttribute('placeholder', t(el.getAttribute('data-i18n-placeholder')));
  });
  root.querySelectorAll('[data-i18n-title]').forEach(el => {
    el.setAttribute('title', t(el.getAttribute('data-i18n-title')));
  });
  root.querySelectorAll('[data-i18n-alt]').forEach(el => {
    el.setAttribute('alt', t(el.getAttribute('data-i18n-alt')));
  });
}
