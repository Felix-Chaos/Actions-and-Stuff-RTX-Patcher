// English -- the canonical locale and the fallback for every other language.
//
// * This file is the source of truth: a value here must match the English text
// * it replaced, character for character, because English is live output too.
// * Keep the key order grouped by app section, matching .agents/I18N.md.
export default {
  common: {
    cancel: 'Cancel',
    ok: 'OK',
    browse: 'Browse...',
  },
  tabPatcher: {
    heading: 'Select Patch Mode',
    mode: {
      marketplace: {
        title: 'Marketplace',
        desc: 'Patches your purchased Marketplace pack directly from premium cache',
      },
      zip: {
        title: 'Zip / McPack',
        desc: 'Normalize and patch an external Minecraft pack file',
      },
      custom: {
        title: 'Custom Patch',
        desc: 'Select specific source, target, and .vcdiff patch files manually',
      },
      advancedHint: 'Enable Advanced Mode to use this feature',
    },
    disclaimer: '<strong>Disclaimer:</strong> A valid Actions & Stuff license is required for legal usage of this patcher!',
    version: {
      modeLabel: 'Version Selection Mode:',
      autoDetect: 'Auto-detect',
      manualSelect: 'Manual Select',
      asVersion: 'A&S Version:',
      patchVersion: 'Patch Version:',
      refreshPatches: '<i class="fas fa-rotate"></i> Refresh patch list',
      refreshPatchesTooltip: 'Check the patch library for newly released patches',
      removeDownload: '<i class="fas fa-trash-can"></i> Remove download',
      removeDownloadTooltip: 'Delete this downloaded patch from disk. It will be downloaded again next time it is used.',
    },
    zipMode: {
      inputFile: 'Input File (.zip / .mcpack):',
      noFileSelected: 'No file selected',
    },
    customMode: {
      sourceLabel: 'Source (Folder / ZIP):',
      noSourceSelected: 'No source selected',
      targetLabel: 'Target File (.mcpack / .zip):',
      noTargetSelected: 'No target selected',
      copyPath: 'Copy path to clipboard',
      patchLabel: 'Patch File (.vcdiff):',
      noPatchSelected: 'No patch selected',
    },
    options: {
      cleanOld: 'Delete older patched versions automatically',
    },
    actions: {
      applyPatch: 'Apply RTX Patch',
      installPack: 'Install Pack',
      copyLog: '📋 Copy Log',
      reportBug: '🐞 Report Bug',
      backToSelection: 'Back to Selection',
    },
    status: {
      heading: 'Patch Status',
      readyTitle: 'Ready to Patch',
      readySubtitle: 'Configure options and click Apply',
    },
    steps: {
      scan: 'Scan / Verify source contents',
      normalize: 'Deterministic compression & normalization',
      cleanOld: 'Clean older versions',
      ensurePatch: 'Ensure patch file is available',
      executePatch: 'Execute XDelta RTX patch',
      importPack: 'Import Minecraft Pack',
    },
    console: {
      heading: 'Execution Output',
      copyTooltip: 'Copy log to clipboard',
      clearTooltip: 'Clear console',
      resizeGripTooltip: 'Drag down to enlarge the console. Double-click to reset.',
    },
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
  nav: {
    patcher: 'Patcher',
    cleaner: 'Cleaner',
    rtxSettings: 'RTX Settings',
    utils: {
      label: 'Utilities',
      pack: 'ZIP Packer',
      extract: 'Extract ZIP',
      genpatch: 'Create Patch',
      brarchive: 'Ext Brarchives',
    },
    support: 'Support',
    release: 'Release',
    appSettings: 'App Settings',
  },
  sidebar: {
    toggle: 'Toggle Sidebar',
    advancedMode: 'Advanced Mode',
    betaUpdates: 'Beta Updates',
    language: 'Language',
    update: {
      checking: 'Checking...',
      upToDate: 'Up to Date',
      available: 'v{version} Available',
      updateNow: 'Update Now',
      updating: 'Updating...',
      checkFailed: 'Check Failed',
    },
  },
  tabAppSettings: {
    language: {
      label: 'Language',
      hint: 'Log and console output stays in English.',
    },
  },
};
