// English -- the canonical locale and the fallback for every other language.
//
// * This file is the source of truth: a value here must match the English text
// * it replaced, character for character, because English is live output too.
// * Keep the key order grouped by app section, matching .agents/I18N.md.
export default {
  sidebar: {
    language: 'Language',
  },
  tabAppSettings: {
    language: {
      label: 'Language',
      hint: 'Log and console output stays in English.',
    },
  },
};
