// Minimal i18n engine for the patcher.
//
// The frontend is served unbundled (tauri.conf.json -> frontendDist: "../src").
// Locales are JSON files, the format translation platforms read and write, and
// are fetched from the app's own origin: no bundler, no import attributes, no
// CSP change.
//
// * Log lines are translated on screen but always copied/exported in English.
// * See .agents/I18N.md for the rule and for LogMessage below.
import { LOCALES, FALLBACK_LOCALE, BUNDLES } from './registry.js';
import { flatten } from './flatten.js';

let current = FALLBACK_LOCALE;
let dict = {};
let fallbackDict = {};
let ready = false;
const listeners = new Set();

async function loadBundle(code, bundle) {
  const res = await fetch(new URL(`./${bundle.path(code)}`, import.meta.url));
  if (res.ok) return flatten(await res.json());
  // ! The fallback must be complete. Any other language may lack a bundle
  // ! (e.g. a freshly added language): its keys then fall back to English.
  if (code === FALLBACK_LOCALE) {
    throw new Error(`[i18n] could not load ${bundle.name} bundle for ${code}: ${res.status}`);
  }
  console.warn(`[i18n] no ${bundle.name} bundle for ${code} (${res.status}), using ${FALLBACK_LOCALE}`);
  return {};
}

async function loadDict(code) {
  const entry = LOCALES.find(l => l.code === code)
    ?? LOCALES.find(l => l.code === FALLBACK_LOCALE);
  const parts = await Promise.all(BUNDLES.map(b => loadBundle(entry.code, b)));
  return Object.assign({}, ...parts);
}

/** Load the fallback plus the requested locale and translate the document once. */
export async function initI18n(initialLocale) {
  fallbackDict = await loadDict(FALLBACK_LOCALE);
  current = LOCALES.some(l => l.code === initialLocale) ? initialLocale : FALLBACK_LOCALE;
  dict = current === FALLBACK_LOCALE ? fallbackDict : await loadDict(current);
  ready = true;
  document.documentElement.lang = current;
  applyTranslations(document);
}

/**
 * A translatable message that is rendered late: once on screen in the active
 * language (and again on every language switch), and in English whenever it
 * leaves the app (copy log, bug report). Used for every console/log line.
 *
 * `fallback` is shown if the key is unknown, e.g. a backend line whose key is
 * newer than the frontend's locale files.
 */
export class LogMessage {
  constructor(key, vars, fallback) {
    this.key = key;
    this.vars = vars;
    this.fallback = fallback;
  }

  // * Anything that stringifies a message (a thrown one in `${err}`, an
  // * alert) gets English, the same as the copied log.
  toString() {
    return renderMessage(this, { english: true });
  }
}

/** Shorthand for `new LogMessage(key, vars)`. */
export function msg(key, vars) {
  return new LogMessage(key, vars);
}

/** Plural variant of `msg`, mirroring `tPlural`. */
export function msgPlural(key, n, vars = {}) {
  return new LogMessage(`${key}.${n === 1 ? 'one' : 'other'}`, { count: n, ...vars });
}

function lookup(key, english) {
  return english ? fallbackDict[key] : (dict[key] ?? fallbackDict[key]);
}

function interpolate(str, vars, english) {
  if (!vars) return str;
  for (const [k, v] of Object.entries(vars)) {
    // A var may itself be a message (e.g. a thrown error), rendered in the same language.
    const text = v instanceof LogMessage ? renderMessage(v, { english }) : String(v);
    str = str.replaceAll(`{${k}}`, text);
  }
  return str;
}

function translate(key, vars, english) {
  const str = lookup(key, english);
  if (str === undefined) {
    // ! A missing key means the locale file and the call site drifted apart.
    // ? Before initI18n nothing is loaded yet; that is not drift.
    if (ready) console.warn(`[i18n] missing key: ${key}`);
    return key;
  }
  return interpolate(str, vars, english);
}

/** Translate `key`, replacing every {name} placeholder from `vars`. */
export function t(key, vars) {
  return translate(key, vars, false);
}

/** Like `t`, but always English, whatever language is active. */
export function tEn(key, vars) {
  return translate(key, vars, true);
}

/**
 * Singular/plural variant of `t`: resolves `<key>.one` or `<key>.other` and
 * pre-fills {count}. English and German both split only on n === 1 here, so
 * full CLDR plural rules would be dead weight.
 */
export function tPlural(key, n, vars = {}) {
  return t(`${key}.${n === 1 ? 'one' : 'other'}`, { count: n, ...vars });
}

/** Render a LogMessage (or pass any other value through as text). */
export function renderMessage(m, { english = false } = {}) {
  if (!(m instanceof LogMessage)) return String(m);
  if (m.fallback !== undefined && fallbackDict[m.key] === undefined) {
    return interpolate(m.fallback, m.vars, english);
  }
  return translate(m.key, m.vars, english);
}

/** Currently active language code. */
export function getLocale() {
  return current;
}

/** Every selectable language, for building the dropdowns. */
export function getLocales() {
  return LOCALES.map(({ code, label, flag }) => ({ code, label, flag }));
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
  // For prose that carries inline formatting (<b>, <code>, <br>). The value
  // comes from our own locale files, never from user input or the network.
  // ! Never put this on an element containing a button, input, or anything
  // ! main.js binds a listener to: rewriting innerHTML destroys those nodes.
  root.querySelectorAll('[data-i18n-html]').forEach(el => {
    el.innerHTML = t(el.getAttribute('data-i18n-html'));
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
  // * Icon-only controls carry their name here instead of as visible text.
  root.querySelectorAll('[data-i18n-aria-label]').forEach(el => {
    el.setAttribute('aria-label', t(el.getAttribute('data-i18n-aria-label')));
  });
}
