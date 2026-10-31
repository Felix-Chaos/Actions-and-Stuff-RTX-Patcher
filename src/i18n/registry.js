// Registry of every language the patcher ships.
//
// To add a language:
//   1. Create locales/<code>.json and locales/dev/<code>.json with the same key
//      shape as their English counterparts. Keys you have not translated yet
//      fall back to English on their own, so a partial (or even missing) file
//      is safe to ship. Translations come in through Crowdin (crowdin.yml),
//      which writes these files; only the English files are edited by hand.
//   2. Add one line to LOCALES below, with a flag image from src/assets/flags
//      (the sidebar picker shows only the flag while it is closed).
// Nothing else changes: both language dropdowns are built from this array at
// runtime, so neither index.html nor main.js needs touching.
export const LOCALES = [
  { code: 'en', label: 'English', flag: 'assets/flags/gb.svg' },
  { code: 'de', label: 'Deutsch', flag: 'assets/flags/de.svg' },
  // The dev bundle is still partial; its missing keys fall back to English.
  { code: 'pt-BR', label: 'Português (Brasil)', flag: 'assets/flags/br.svg', partialBundles: ['dev'] },
];

// The language every lookup falls back to. Its locale files must be complete.
export const FALLBACK_LOCALE = 'en';

// Every language is split into bundles, one file each, merged into a single
// key space at runtime. A key may live in exactly one bundle, so moving a key
// between bundles never changes a call site or a data-i18n attribute.
//   ui  -- everything an end user sees.
//   dev -- console/log output plus the author-only tools (Create Patch,
//          publishing, Release Builder, diagnostics), kept apart so
//          translators can prioritise the user-facing file. The Rust backend
//          embeds dev/en.json for its own log lines (src-tauri/src/logmsg.rs).
// Paths are relative to src/i18n/.
export const BUNDLES = [
  { name: 'ui', path: code => `locales/${code}.json` },
  { name: 'dev', path: code => `locales/dev/${code}.json` },
];
