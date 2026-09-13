// English -- the canonical locale and the fallback for every other language.
//
// * This file is the source of truth: a value here must match the English text
// * it replaced, character for character, because English is live output too.
// * Keep the key order grouped by app section, matching .agents/I18N.md.
export default {
  common: {
    cancel: 'Cancel',
    ok: 'OK',
  },
  modal: {
    notificationTitle: 'Notification',
    confirmTitle: 'Confirm',
    telemetryConsent: {
      title: 'Help Us Diagnose Rare RTX Issues',
      intro: 'Certain rendering issues occur only on specific GPU and driver combinations. With your consent, the patcher can submit a <b>pseudonymous hardware summary</b>',
      whatsTheDifference: "what's the difference?",
      introAfter: 'to help identify these cases. Reporting is opt-in and is requested once, on first launch. Afterward, your hardware is checked on every launch, and a new submission is sent only when the result differs from the previous one, for example after a GPU, driver, or BetterRTX preset change:',
      notCollected: '<b>Not collected:</b> your name, files, or serial numbers. Each submission is identified by a randomly generated <b>installation ID</b> and a one-way hash derived from your machine, used solely to recognize repeat submissions from the same installation so it is not counted twice after a reinstall. Because these identifiers persist and link submissions over time, this is described as pseudonymous rather than anonymous. Both identifiers can be deleted at any time from Settings under "Delete My Data," which also removes the corresponding record from the server. Every payload is additionally saved locally as <code>last_hardware_ping.json</code> for review. Uploaded bug-report logs are deleted after 30 days.',
      point1: 'GPU model, driver version & VRAM',
      point2: 'CPU model, RAM size, Windows build',
      point3: 'Minecraft edition (Store / Launcher) & patcher version',
      decline: 'Decline',
      accept: 'Enable Reporting',
    },
  },
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
