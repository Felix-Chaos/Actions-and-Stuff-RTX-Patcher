// Registry of every language the patcher ships.
//
// To add a language:
//   1. Create locales/<code>.json with the same key shape as locales/en.json.
//      Keys you have not translated yet fall back to English on their own, so a
//      partial file is safe to ship. Translations come in through Crowdin
//      (crowdin.yml), which writes these files; only en.json is edited by hand.
//   2. Add one line to LOCALES below, with a flag image from src/assets/flags
//      (the sidebar picker shows only the flag while it is closed).
// Nothing else changes: both language dropdowns are built from this array at
// runtime, so neither index.html nor main.js needs touching.
export const LOCALES = [
  { code: 'en', label: 'English', flag: 'assets/flags/gb.svg' },
  { code: 'de', label: 'Deutsch', flag: 'assets/flags/de.svg' },
];

// The language every lookup falls back to. Its locale file must be complete.
export const FALLBACK_LOCALE = 'en';
