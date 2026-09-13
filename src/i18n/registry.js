// Registry of every language the patcher ships.
//
// To add a language:
//   1. Create locales/<code>.js exporting the same key shape as locales/en.js.
//      Keys you have not translated yet fall back to English on their own, so a
//      partial file is safe to ship.
//   2. Add one line to LOCALES below.
// Nothing else changes: both language dropdowns are built from this array at
// runtime, so neither index.html nor main.js needs touching.
export const LOCALES = [
  { code: 'en', label: 'English', loader: () => import('./locales/en.js') },
  { code: 'de', label: 'Deutsch', loader: () => import('./locales/de.js') },
];

// The language every lookup falls back to. Its locale file must be complete.
export const FALLBACK_LOCALE = 'en';
