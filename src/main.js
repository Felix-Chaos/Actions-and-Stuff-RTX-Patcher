// JavaScript Controller for Actions & Stuff RTX Patcher v3

import { initI18n, setLocale, getLocale, getLocales, onLocaleChange, t, tEn, tPlural, msg, msgPlural, renderMessage, LogMessage } from './i18n/index.js';

// applyTranslations only reaches text annotated in index.html. Anything a
// function writes into the DOM at runtime keeps the language it was rendered
// in until that function runs again, so those regions are rebuilt here.
//
// * Re-render from state already in memory only. Nothing here may touch the
// * network or the backend: switching language stays instant and works offline.
onLocaleChange(() => {
  // ? Each region is guarded on its own. One that is not built yet, or throws,
  // ? must not leave the rest of the page stuck in the previous language.
  const regions = [
    // The update badge interpolates a version number, so it cannot be restored
    // from a data-i18n key alone; it remembers the version instead.
    () => {
      const badge = document.getElementById('update-badge');
      if (badge?.dataset.updateVersion) {
        badge.innerText = t('sidebar.update.available', { version: badge.dataset.updateVersion });
      }
    },
    () => {
      const asSel = document.getElementById('select-as-version');
      if (!asSel) return;
      Array.from(asSel.options).forEach(opt => {
        opt.innerText = t('tabPatcher.version.versionOption', { version: opt.value });
      });
      if (asSel.value) updatePatchVersionsList(asSel.value);
    },
    () => updateMotdBox(),
    () => updateSelectedPatchAvailability(),
    () => renderDownloadedPatchesSettings(),
    () => renderCleanerResults(),
    () => updateCleanerButtons(),
    () => updateConsoleHeightReadout(appSettings.consoleHeight),
    () => repaintLogLines(),
  ];

  for (const region of regions) {
    try {
      region();
    } catch (e) {
      console.warn('[i18n] re-render failed:', e);
    }
  }
});

// Destructure invoke and listen from Tauri Core
const { invoke, Channel } = window.__TAURI__ ? window.__TAURI__.core : { invoke: () => Promise.reject("Tauri not available"), Channel: class {} };
const { listen } = window.__TAURI__ ? window.__TAURI__.event : { listen: () => {} };

// Listen for backend log messages and route them to correct UI console
if (window.__TAURI__) {
  listen('app-log', (event) => {
    const { container, message, log_type, key, vars } = event.payload;
    // Keyed backend lines translate like any other; `message` is their English
    // text, shown as is if this frontend does not know the key.
    const line = key ? new LogMessage(key, vars, message) : message;
    if (container === 'main') {
      log(line, log_type);
    } else {
      logTo(container, line, log_type);
    }
  });
}

function showModal(message, options = {}) {
  const {
    title = t('modal.notificationTitle'),
    confirm = false,
    okText = t('common.ok'),
    cancelText = t('common.cancel')
  } = options;

  return new Promise((resolve) => {
    const modal = document.getElementById('custom-modal');
    const titleEl = document.getElementById('modal-title');
    const messageEl = document.getElementById('modal-message');
    const okBtn = document.getElementById('btn-modal-ok');
    const cancelBtn = document.getElementById('btn-modal-cancel');

    if (!modal || !messageEl || !okBtn || !cancelBtn) {
      console.warn("Custom modal missing; fallback log: ", message);
      resolve(false);
      return;
    }

    if (titleEl) titleEl.innerText = title;
    messageEl.innerText = message;
    okBtn.innerText = okText;
    cancelBtn.innerText = cancelText;

    if (confirm) {
      cancelBtn.classList.remove('hidden-group');
    } else {
      cancelBtn.classList.add('hidden-group');
    }

    const cleanup = () => {
      modal.classList.add('hidden-group');
      okBtn.onclick = null;
      cancelBtn.onclick = null;
    };

    okBtn.onclick = () => {
      cleanup();
      resolve(true);
    };

    cancelBtn.onclick = () => {
      cleanup();
      resolve(false);
    };

    modal.classList.remove('hidden-group');
  });
}

// Returns the promise so callers can await dismissal. Existing fire-and-forget
// callers are unaffected.
function showAlert(message, title = t('modal.notificationTitle')) {
  return showModal(message, { title, confirm: false });
}

async function showConfirm(message, title = t('modal.confirmTitle')) {
  return showModal(message, { title, confirm: true });
}

// Override window.alert to use the in-app modal
window.alert = function(msg) {
  showAlert(msg);
};

// window.confirm cannot be redirected to the in-app modal, because it must
// return synchronously while the modal resolves a promise. Anything reaching
// this has to be rewritten as `await showConfirm(...)`; deny in the meantime,
// so a stray call can never silently approve a destructive action.
window.confirm = function(msg) {
  console.error("window.confirm is not supported in this app - use `await showConfirm(...)` instead. Denied:", msg);
  showAlert(msg, t('modal.confirmTitle'));
  return false;
};

// Global State
let patchConfigs = [];
// Slugs of patches downloaded into this user's cache, plus their sizes.
let cachedPatchSlugs = new Set();
let cachedPatchVariants = new Map(); // slug -> Set of cached variants
let cachedPatchInfo = [];
let optionsProfiles = [];
let selectedOptionsPath = "";
let defaultPaths = {};

// UI Elements
const tabs = document.querySelectorAll('.nav-tab');
const tabContents = document.querySelectorAll('.tab-content');
const modeRadios = document.querySelectorAll('input[name="patch-mode"]');
const customInputsGroup = document.getElementById('custom-inputs-group');
const versionSelectGroup = document.getElementById('version-select-group');
const consoleLogs = document.getElementById('console-logs');

// Console Log Helpers
//
// A log line is a LogMessage (see i18n/index.js), or a plain string for text
// that is data rather than prose (raw backend/tool output, error text). Each
// line keeps its message, so it is shown in the active language, repainted on
// a language switch, and copied or exported in English.
function logLineText(line, english = false) {
  const entry = line._log;
  if (entry) {
    const text = renderMessage(entry.msg, { english });
    return entry.time ? `[${entry.time}] ${text}` : text;
  }
  // Static placeholder lines carry a plain data-i18n key instead.
  const key = line.getAttribute('data-i18n');
  if (key) return english ? tEn(key) : t(key);
  return line.innerText;
}

function makeLogLine(m, type, { timestamp = true } = {}) {
  const line = document.createElement('div');
  line.className = `log-line ${type}`;
  line._log = { msg: m, time: timestamp ? new Date().toLocaleTimeString() : null };
  line.innerText = logLineText(line);
  return line;
}

function appendLogLine(el, m, type) {
  el.appendChild(makeLogLine(m, type));
  el.scrollTop = el.scrollHeight;
}

// Empties a console down to one untimed status line.
function resetLog(el, m, type = 'system') {
  if (!el) return;
  el.replaceChildren(makeLogLine(m, type, { timestamp: false }));
}

function repaintLogLines() {
  document.querySelectorAll('.log-line').forEach(line => {
    if (line._log) line.innerText = logLineText(line);
  });
}

// Every log line under `root`, in English, one per line.
function englishLogText(root = document) {
  return Array.from(root.querySelectorAll('.log-line'))
    .map(l => logLineText(l, true)).join('\n');
}

function log(m, type = 'info') {
  appendLogLine(consoleLogs, m, type);
}

// Shows a busy label on a button while `fn` runs. A button that carries an
// i18n key gets its idle label back from the locale rather than from a
// snapshot, so a language switch made mid-run is not undone.
async function withBusyLabel(btn, busyHtml, fn) {
  const original = btn.innerHTML;
  btn.innerHTML = busyHtml;
  try {
    return await fn();
  } finally {
    const htmlKey = btn.getAttribute('data-i18n-html');
    const textKey = btn.getAttribute('data-i18n');
    if (htmlKey) btn.innerHTML = t(htmlKey);
    else if (textKey) btn.textContent = t(textKey);
    else btn.innerHTML = original;
  }
}

function logTo(container, m, type = 'info') {
  const el = document.getElementById(container);
  if (!el) return;
  appendLogLine(el, m, type);
}

function clearConsole() {
  resetLog(consoleLogs, msg('log.placeholder.cleared'));
}

// Update Status Helper
function updateStatus(title, subtitle, icon = '⏳') {
  document.getElementById('status-title-text').innerText = title;
  document.getElementById('status-subtitle-text').innerText = subtitle;
  document.getElementById('status-spinner').innerText = icon;
}

function updateProgress(percent) {
  document.getElementById('patch-progress-fill').style.width = `${percent}%`;
  document.getElementById('patch-percent-text').innerText = `${percent}%`;
}

function updateStepState(stepId, state) {
  const step = document.getElementById(`step-${stepId}`);
  if (!step) return;
  
  step.className = `step-item ${state}`;
  const indicator = step.querySelector('.step-indicator');
  if (state === 'active') {
    indicator.innerText = '⚡';
  } else if (state === 'completed') {
    indicator.innerText = '✅';
  } else if (state === 'failed') {
    indicator.innerText = '❌';
  } else {
    indicator.innerText = '⚪';
  }
}

function resetSteps() {
  for (let i = 0; i <= 5; i++) {
    updateStepState(i, 'idle');
  }
}

// Copy log helper. Always copies English, whatever language is on screen, so
// pasted logs read the same for whoever has to debug them.
function copyLogsFromEl(elId, btnId) {
  const el = document.getElementById(elId);
  const btn = document.getElementById(btnId);
  if (!el) return;
  const text = englishLogText(el);
  navigator.clipboard.writeText(text).then(() => {
    if (btn) {
      btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fbbf24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-check"><path d="M20 6 9 17l-5-5"/></svg>`;
      setTimeout(() => {
        btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-copy"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`;
      }, 2000);
    }
  }).catch(() => {});
}

// Tab Navigation
tabs.forEach(tab => {
  tab.addEventListener('click', () => {
    if (!tab.classList.contains('nav-dropdown-toggle')) {
      const subtabs = document.querySelectorAll('.nav-subtab');
      subtabs.forEach(st => st.classList.remove('active'));
    }
    
    tabs.forEach(t => t.classList.remove('active'));
    tabContents.forEach(tc => tc.classList.remove('active'));
    
    tab.classList.add('active');
    const targetTab = document.getElementById(`tab-${tab.dataset.tab}`);
    if (targetTab) {
      targetTab.classList.add('active');
    }
  });
});

// Patcher Mode Switching
modeRadios.forEach(radio => {
  radio.addEventListener('change', () => {
    const val = radio.value;
    const zipFileGroup = document.getElementById('zip-file-group');
    
    if (val === 'custom') {
      customInputsGroup.classList.remove('hidden-group');
      versionSelectGroup.classList.add('hidden-group');
      if (zipFileGroup) zipFileGroup.classList.add('hidden-group');
    } else if (val === 'zip') {
      customInputsGroup.classList.add('hidden-group');
      versionSelectGroup.classList.remove('hidden-group');
      if (zipFileGroup) zipFileGroup.classList.remove('hidden-group');
    } else {
      customInputsGroup.classList.add('hidden-group');
      if (zipFileGroup) zipFileGroup.classList.add('hidden-group');
    }

    // Update MOTD Display based on selected mode
    if (typeof updateMotdBox === 'function') {
      updateMotdBox();
    }

    // Toggle disclaimer visibility
    const disclaimer = document.querySelector('.disclaimer-box');
    if (disclaimer) {
      if (val === 'zip' || val === 'custom') {
        disclaimer.classList.remove('hidden-group');
      } else {
        disclaimer.classList.add('hidden-group');
      }
    }
  });
});

// Load MOTD
window.loadedMotds = {};

function updateMotdBox() {
  const motdContainer = document.getElementById('motd-container');
  const motdTitle = document.getElementById('motd-title');
  const motdMessage = document.getElementById('motd-message');

  const mode = document.querySelector('input[name="patch-mode"]:checked')?.value || 'global';
  let activeMotd = window.loadedMotds[mode];
  
  if (!activeMotd || !activeMotd.title) {
    activeMotd = window.loadedMotds['global'];
  }

  if (activeMotd && activeMotd.title) {
    const toText = (s) => (s || "").replace(/\\n/g, "\n");
    if (motdTitle) motdTitle.innerText = toText(activeMotd.title);
    if (motdMessage) motdMessage.innerText = toText(activeMotd.message);
    if (motdContainer) motdContainer.classList.remove('hidden-group');
  } else {
    if (motdContainer) motdContainer.classList.add('hidden-group');
  }
}

async function loadMotd() {
  const offlineContainer = document.getElementById('motd-offline-container');
  const offlineTitle = document.getElementById('motd-offline-title');
  const offlineMessage = document.getElementById('motd-offline-message');

  try {
    const res = await invoke("fetch_motd");
    if (res && res.success && res.motds) {
      window.loadedMotds = res.motds;
      updateMotdBox();
      
      if (offlineContainer) {
        try {
          const isDev = await invoke("is_dev_build");
          if (isDev) {
            if (offlineTitle) offlineTitle.innerText = t('tabPatcher.motd.offlineDevPreviewTitle');
            if (offlineMessage) offlineMessage.innerText = t('tabPatcher.motd.offlineDevPreviewMessage');
            offlineContainer.classList.remove('hidden-group');
          } else {
            offlineContainer.classList.add('hidden-group');
          }
        } catch (e) {
          offlineContainer.classList.add('hidden-group');
        }
      }
    } else if (res && res.success && res.motd) {
      // Fallback for old bot response
      window.loadedMotds = { global: res.motd };
      updateMotdBox();
    }
  } catch (err) {
    console.warn("Could not fetch MOTD:", err);
    // ! motdContainer belongs to updateMotdBox, not to this function. Reading it
    // ! here threw a ReferenceError that aborted the whole offline branch below.
    const motdContainer = document.getElementById('motd-container');
    if (motdContainer) motdContainer.classList.add('hidden-group'); // Hide from main page
    
    if (offlineContainer && offlineTitle) {
      try {
        const isDev = await invoke("is_dev_build");
        if (isDev) {
          offlineTitle.innerText = t('tabPatcher.motd.offlineDevTitle');
          if (offlineMessage) offlineMessage.innerText = t('tabPatcher.motd.offlineDevMessage');
          offlineContainer.classList.remove('hidden-group');
        } else {
          // Completely remove/hide the text in release version
          offlineContainer.classList.add('hidden-group');
        }
      } catch (e) {
        offlineContainer.classList.add('hidden-group');
      }
    }
  }
}

// Folder of the most recently created patch, so it can be published without
// regenerating it.
let lastCreatedPatchFolder = "";

// Collects the creator/title/description for a publish PR, pre-filled from
// whatever was used last time so the maintainer isn't retyping the same
// details on every patch. Resolves null on cancel.
function showPublishDetailsForm({ creator = '', title = '', description = '' } = {}) {
  return new Promise((resolve) => {
    const modal = document.getElementById('publish-patch-modal');
    const creatorEl = document.getElementById('publish-creator');
    const titleEl = document.getElementById('publish-title');
    const descEl = document.getElementById('publish-description');
    const okBtn = document.getElementById('btn-publish-modal-ok');
    const cancelBtn = document.getElementById('btn-publish-modal-cancel');

    if (!modal || !creatorEl || !titleEl || !descEl || !okBtn || !cancelBtn) {
      console.warn("Publish details modal missing.");
      resolve(null);
      return;
    }

    creatorEl.value = creator;
    titleEl.value = title;
    descEl.value = description;

    const cleanup = () => {
      modal.classList.add('hidden-group');
      okBtn.onclick = null;
      cancelBtn.onclick = null;
    };

    okBtn.onclick = () => {
      const result = {
        creator: creatorEl.value.trim(),
        title: titleEl.value.trim(),
        description: descEl.value.trim(),
      };
      cleanup();
      resolve(result);
    };
    cancelBtn.onclick = () => { cleanup(); resolve(null); };

    modal.classList.remove('hidden-group');
    titleEl.focus();
  });
}

// Copies a created patch folder into the patch library clone and opens a
// pull request for it, so CI there (hashing, upload, catalogue rebuild) runs
// against a reviewable change instead of a direct push to main.
async function publishPatchToLibrary(patchFolder, { packVer, patchVer } = {}) {
  const gLog = (m, type = 'info') => logTo('genpatch-logs', m, type);
  const libraryDir = appSettings.patchLibraryDir;

  if (!libraryDir) {
    gLog(msg('log.publish.noLibraryFolder'), 'warning');
    await showAlert(
      t('tabPatcher.publish.noLibraryFolderMessage'),
      t('tabPatcher.publish.noLibraryFolderTitle')
    );
    return false;
  }

  const name = patchFolder.split(/[\\/]/).pop() || patchFolder;
  const defaultTitle = packVer && patchVer
    ? `Publish Actions & Stuff for RTX ${packVer} v${patchVer}`
    : (appSettings.lastPatchPrTitle || `Publish ${name}`);

  const details = await showPublishDetailsForm({
    creator: appSettings.patchCreatorName || '',
    title: defaultTitle,
    description: appSettings.lastPatchPrDescription || '',
  });
  if (!details) { gLog(msg('log.publish.cancelled'), 'warning'); return false; }

  const { creator, title, description } = details;
  // Remembered for next time, so these fields don't need retyping.
  appSettings.patchCreatorName = creator;
  appSettings.lastPatchPrTitle = title;
  appSettings.lastPatchPrDescription = description;
  await saveSettings();

  const attempt = async (overwrite) => invoke("publish_patch_to_library", {
    libraryDir, patchFolder, creator, title, description, overwrite
  });

  const openPr = async (prUrl) => {
    gLog(msg('log.publish.openedPr', { url: prUrl }), 'success');
    await showAlert(t('tabPatcher.publish.openedMessage', { url: prUrl }), t('tabPatcher.publish.openedTitle'));
    try { await invoke("open_url", { url: prUrl }); } catch (_) {}
  };

  try {
    const prUrl = await attempt(false);
    await openPr(prUrl);
  } catch (err) {
    const text = String(err);
    if (!text.includes("ALREADY_EXISTS")) {
      gLog(msg('log.publish.failed', { error: text }), 'error');
      await showAlert(
        t('tabPatcher.publish.failedMessage', { error: text }),
        t('tabPatcher.publish.failedTitle')
      );
      return false;
    }
    // Already in the library: a PR that replaces the payloads is a real thing
    // to want after rebuilding a patch, but never silent.
    const replace = await showConfirm(
      t('tabPatcher.publish.alreadyPublishedMessage', { name }),
      t('tabPatcher.publish.alreadyPublishedTitle')
    );
    if (!replace) { gLog(msg('log.publish.cancelledKept'), 'warning'); return false; }
    try {
      const prUrl = await attempt(true);
      await openPr(prUrl);
    } catch (err2) {
      gLog(msg('log.publish.failed', { error: err2 }), 'error');
      await showAlert(
        t('tabPatcher.publish.failedMessage', { error: err2 }),
        t('tabPatcher.publish.failedTitle')
      );
      return false;
    }
  }

  return true;
}

// Catalogue auto-refresh. A patch published while the app is open should show
// up on its own, but the catalogue must not be re-fetched on every stray focus
// event, and never mid-run.
const CATALOGUE_POLL_MS = 15 * 60 * 1000;   // periodic check while the app is open
const CATALOGUE_MIN_GAP_MS = 60 * 1000;     // floor between any two automatic checks
let lastCatalogueStamp = null;
let lastCatalogueCheck = 0;
let knownPatchKeys = null;
let catalogueRefreshInFlight = false;

function patchConfigsKeys(configs) {
  return configs.map(c => `${c.packVersion}|${c.patchVersion || "1.0"}`);
}

// Briefly highlights the version controls so a change is noticed even if the
// console is scrolled away.
function flashPatchListUpdated(count) {
  const hint = document.getElementById('patch-availability-hint');
  if (!hint) return;
  const msg = tPlural('tabPatcher.version.newPatchesAvailable', count);
  hint.dataset.flash = 'true';
  hint.innerHTML = `<span style="color:#7ed17e;">${msg}</span>`;
  // Hand the hint back to the normal availability text after a moment.
  setTimeout(() => {
    if (hint.dataset.flash) {
      delete hint.dataset.flash;
      updateSelectedPatchAvailability();
    }
  }, 6000);
}

function patchRunInProgress() {
  const btn = document.getElementById('btn-start-patch');
  return !!(btn && btn.disabled);
}

// Re-checks the catalogue if enough time has passed. Silent by design: it logs
// only when something actually changed.
async function autoRefreshCatalogue(reason) {
  if (catalogueRefreshInFlight) return;
  if (patchRunInProgress()) return;                       // never disturb a running patch
  if (Date.now() - lastCatalogueCheck < CATALOGUE_MIN_GAP_MS) return;

  catalogueRefreshInFlight = true;
  lastCatalogueCheck = Date.now();
  const before = lastCatalogueStamp;
  try {
    await loadPatchConfigs({ quiet: true });
    await refreshCachedPatches();
    if (before !== lastCatalogueStamp) {
      console.log(`Patch catalogue refreshed (${reason}); updated ${lastCatalogueStamp}`);
    }
  } catch (err) {
    console.error("Automatic catalogue refresh failed", err);
  } finally {
    catalogueRefreshInFlight = false;
  }
}

function setupCatalogueAutoRefresh() {
  // Coming back to the window is the moment a newly published patch is most
  // likely to matter, and it costs one small request.
  window.addEventListener('focus', () => autoRefreshCatalogue('window focus'));

  // Opening the Patcher tab, for a long-running window that never loses focus.
  document.querySelectorAll('.nav-tab[data-tab="patcher"]').forEach(tab => {
    tab.addEventListener('click', () => autoRefreshCatalogue('patcher tab'));
  });

  setInterval(() => autoRefreshCatalogue('periodic'), CATALOGUE_POLL_MS);
}

// Load configs and versions from Rust.
// Safe to call more than once: it only rebuilds the dropdowns. The one-time
// event wiring lives in wireVersionControls().
async function loadPatchConfigs({ quiet = false } = {}) {
  const say = (m, type) => { if (!quiet) log(m, type); };
  let newlyAdded = 0;
  try {
    say(msg('log.catalogue.loading'));
    const bundled = await invoke("get_patch_configs");
    say(msg('log.catalogue.bundledFound', { count: bundled.length }));

    // Merge in the remote patch library. Bundled entries win on conflict, so a
    // patch shipped inside the installer is always preferred over downloading
    // the same version again.
    let remote = [];
    try {
      const index = await invoke("fetch_patch_index");
      const bundledKeys = new Set(bundled.map(c => `${c.packVersion}|${c.patchVersion || "1.0"}`));
      remote = (index.entries || []).filter(
        e => !bundledKeys.has(`${e.packVersion}|${e.patchVersion || "1.0"}`)
      );
      say(index.updated
        ? msg('log.catalogue.remoteLoadedUpdated', { count: remote.length, source: index.source, updated: index.updated })
        : msg('log.catalogue.remoteLoaded', { count: remote.length, source: index.source }));
      if (index.source === 'cache') {
        say(msg('log.catalogue.usingCache'), 'warning');
      } else if (index.source === 'none') {
        say(msg('log.catalogue.noCatalogue'), 'warning');
      }
      lastCatalogueStamp = index.updated || null;
    } catch (err) {
      say(msg('log.catalogue.remoteFailed', { error: err }), 'warning');
    }

    // Announce anything that appeared since the last look, so a patch released
    // while the app is open is visible without the user hunting for it.
    const seenBefore = knownPatchKeys;
    const nowKeys = new Set(patchConfigsKeys([...bundled, ...remote]));
    if (seenBefore) {
      const added = [...nowKeys].filter(k => !seenBefore.has(k));
      added.forEach(k => {
        const [pack, patch] = k.split('|');
        log(msg('log.catalogue.newPatch', { pack, patch }), 'success');
      });
      newlyAdded = added.length;
    }
    knownPatchKeys = nowKeys;

    patchConfigs = [...bundled, ...remote];
    say(msg('log.catalogue.totalAvailable', { count: patchConfigs.length }));

    // Extract unique packVersion strings and sort descending
    const uniqueAsVersions = Array.from(new Set(patchConfigs.map(c => c.packVersion)))
      .sort((a, b) => b.localeCompare(a, undefined, { numeric: true, sensitivity: 'base' }));

    const asSelect = document.getElementById('select-as-version');
    if (asSelect) {
      const previous = asSelect.value;
      asSelect.innerHTML = '';
      uniqueAsVersions.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v;
        opt.innerText = t('tabPatcher.version.versionOption', { version: v });
        asSelect.appendChild(opt);
      });
      if (previous && uniqueAsVersions.includes(previous)) asSelect.value = previous;
    }

    const selected = asSelect && asSelect.value ? asSelect.value : uniqueAsVersions[0];
    if (selected) {
      updatePatchVersionsList(selected);
    }

    // After the rebuild, so the notice is not immediately overwritten by it.
    if (newlyAdded) flashPatchListUpdated(newlyAdded);
  } catch (err) {
    log(msg('log.catalogue.loadFailed', { error: err }), 'error');
  }
}

// Console resizing. The section has a fixed height in CSS; dragging the handle
// overrides it and the choice is persisted like any other setting.
const CONSOLE_HEIGHT_DEFAULT = 150;
const CONSOLE_HEIGHT_MIN = 80;

function consoleHeightMax() {
  // Leave room for the rest of the panel on short windows.
  return Math.max(CONSOLE_HEIGHT_MIN, Math.round(window.innerHeight * 0.7));
}

function applyConsoleHeight(px) {
  const section = document.getElementById('main-console-section');
  if (!section) return CONSOLE_HEIGHT_DEFAULT;
  const clamped = Math.min(consoleHeightMax(), Math.max(CONSOLE_HEIGHT_MIN, Math.round(px)));
  section.style.height = `${clamped}px`;
  return clamped;
}

function updateConsoleHeightReadout(px) {
  const readout = document.getElementById('console-height-readout');
  if (readout) readout.innerText = t('tabAppSettings.console.currently', { px });
  document.querySelectorAll('.console-size-preset').forEach(btn => {
    btn.classList.toggle('active', Number(btn.dataset.height) === px);
  });
}

function setConsoleHeight(px, persist = true) {
  const applied = applyConsoleHeight(px);
  updateConsoleHeightReadout(applied);
  if (persist && applied !== appSettings.consoleHeight) {
    appSettings.consoleHeight = applied;
    saveSettings();
  }
  return applied;
}

function setupConsoleResize() {
  const handle = document.getElementById('console-resize-handle');
  const section = document.getElementById('main-console-section');

  // The presets live in Settings and must work even if the console markup
  // changes, so they are wired independently of the drag handle.
  document.querySelectorAll('.console-size-preset').forEach(btn => {
    btn.addEventListener('click', () => setConsoleHeight(Number(btn.dataset.height)));
  });

  if (!handle || !section) return;

  updateConsoleHeightReadout(applyConsoleHeight(appSettings.consoleHeight || CONSOLE_HEIGHT_DEFAULT));

  let startY = 0;
  let startHeight = 0;
  let latest = 0;

  const onMove = (e) => {
    // The grip sits on the bottom edge, so the console follows the cursor:
    // dragging down enlarges it.
    latest = applyConsoleHeight(startHeight + (e.clientY - startY));
    updateConsoleHeightReadout(latest);
  };

  const onUp = () => {
    document.removeEventListener('pointermove', onMove);
    document.removeEventListener('pointerup', onUp);
    handle.classList.remove('dragging');
    document.body.classList.remove('console-resizing');
    if (latest && latest !== appSettings.consoleHeight) {
      appSettings.consoleHeight = latest;
      saveSettings();
    }
    updateConsoleHeightReadout(latest);
  };

  handle.addEventListener('pointerdown', (e) => {
    e.preventDefault();
    startY = e.clientY;
    startHeight = section.getBoundingClientRect().height;
    latest = startHeight;
    handle.classList.add('dragging');
    document.body.classList.add('console-resizing');
    document.addEventListener('pointermove', onMove);
    document.addEventListener('pointerup', onUp);
  });

  handle.addEventListener('dblclick', () => {
    setConsoleHeight(CONSOLE_HEIGHT_DEFAULT);
    log(msg('log.app.consoleHeightReset', { px: CONSOLE_HEIGHT_DEFAULT }));
  });

  // A saved height can exceed the window after a resize or a screen change.
  window.addEventListener('resize', () => {
    if (appSettings.consoleHeight) applyConsoleHeight(appSettings.consoleHeight);
  });
}

// Renders the "Downloaded Patches" list in Settings: one row per cached
// patch with its size and a Remove button, plus a total.
function renderDownloadedPatchesSettings() {
  const list = document.getElementById('downloaded-patches-list');
  const total = document.getElementById('downloaded-patches-total');
  const btnClear = document.getElementById('btn-clear-patch-cache');
  if (!list) return;

  if (cachedPatchInfo.length === 0) {
    list.innerHTML = `<div class="placeholder-text" style="font-size: 0.8rem;">${t('tabPatcher.cache.empty')}</div>`;
    if (total) total.innerText = '';
    if (btnClear) btnClear.disabled = true;
    return;
  }

  if (btnClear) btnClear.disabled = false;
  list.innerHTML = '';

  cachedPatchInfo.forEach(entry => {
    // Map the cache id back to a human name where the catalogue still knows it.
    const config = patchConfigs.find(c => c.slug === entry.slug);
    const label = config
      ? t('tabPatcher.cache.patchLabel', { packVersion: config.packVersion, patchVersion: config.patchVersion || "1.0" })
      : entry.slug;

    const row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:8px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.06);';
    row.innerHTML = `
      <div style="min-width:0;">
        <div style="font-size:0.85rem;color:#ffffff;">${label}</div>
        <div style="font-size:0.72rem;color:#9aa0a6;">${entry.variants.join(', ')} &middot; ${(entry.size / 1048576).toFixed(1)} MB</div>
      </div>
      <button type="button" class="btn btn-secondary btn-xs" data-slug="${entry.slug}">${t('tabPatcher.cache.remove')}</button>
    `;
    row.querySelector('button').addEventListener('click', async (e) => {
      const btn = e.currentTarget;
      btn.disabled = true;
      btn.innerText = t('tabPatcher.cache.removing');
      try {
        const freed = await invoke("delete_cached_patch", { slug: entry.slug });
        log(msg('log.cache.removed', { slug: entry.slug, mb: (freed / 1048576).toFixed(1) }), 'success');
        await refreshCachedPatches();
      } catch (err) {
        log(msg('log.cache.removeFailed', { error: err }), 'error');
        btn.disabled = false;
        btn.innerText = t('tabPatcher.cache.remove');
      }
    });
    list.appendChild(row);
  });

  const bytes = cachedPatchInfo.reduce((sum, e) => sum + e.size, 0);
  if (total) {
    const mb = (bytes / 1048576).toFixed(1);
    total.innerText = tPlural('tabPatcher.cache.summary', cachedPatchInfo.length, { mb });
  }
}

// One-time listener wiring for the version selectors. Kept out of
// loadPatchConfigs so refreshing the catalogue cannot double-bind handlers.
function wireVersionControls() {
  const asSelect = document.getElementById('select-as-version');
  if (asSelect) {
    asSelect.addEventListener('change', (e) => {
      updatePatchVersionsList(e.target.value);
    });
  }

  // Selection mode toggle buttons switch
  const btnAuto = document.getElementById('btn-ver-auto');
  const btnManual = document.getElementById('btn-ver-manual');
  const verModeInput = document.getElementById('version-selection-mode');
  const manualOptions = document.getElementById('manual-version-options');

  if (btnAuto && btnManual && verModeInput && manualOptions) {
    const toggleMode = (mode) => {
      verModeInput.value = mode;
      if (mode === 'auto') {
        btnAuto.classList.add('active');
        btnManual.classList.remove('active');
        manualOptions.classList.add('hidden-group');
      } else {
        btnAuto.classList.remove('active');
        btnManual.classList.add('active');
        manualOptions.classList.remove('hidden-group');
      }
      verModeInput.dispatchEvent(new Event('change'));
    };

    btnAuto.addEventListener('click', () => toggleMode('auto'));
    btnManual.addEventListener('click', () => toggleMode('manual'));
  }

  // Keep the availability hint in step with the selected patch version.
  const patchSelect = document.getElementById('select-patch-version');
  if (patchSelect) {
    patchSelect.addEventListener('change', () => updateSelectedPatchAvailability());
    // Which variant counts as downloaded depends on the mode, so repaint on a switch.
    modeRadios.forEach(radio => radio.addEventListener('change', () => {
      const asSel = document.getElementById('select-as-version');
      if (asSel && asSel.value) updatePatchVersionsList(asSel.value);
    }));
  }

  // Manual refresh, so a patch published minutes ago can be picked up without
  // restarting the app.
  const btnRefresh = document.getElementById('btn-refresh-patches');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', async () => {
      btnRefresh.disabled = true;
      try {
        await withBusyLabel(btnRefresh, `<i class="fas fa-spinner fa-spin"></i> ${t('tabPatcher.version.refreshing')}`, async () => {
          await loadPatchConfigs();
          await refreshCachedPatches();
        });
      } finally {
        btnRefresh.disabled = false;
      }
    });
  }

  // Remove just the patch currently selected in the version list.
  const btnRemoveSelected = document.getElementById('btn-remove-selected-patch');
  if (btnRemoveSelected) {
    btnRemoveSelected.addEventListener('click', async () => {
      const slug = btnRemoveSelected.dataset.slug;
      if (!slug) return;
      btnRemoveSelected.disabled = true;
      try {
        const freed = await invoke("delete_cached_patch", { slug });
        log(msg('log.cache.removedRedownload', { slug, mb: (freed / 1048576).toFixed(1) }), 'success');
        await refreshCachedPatches();
      } catch (err) {
        log(msg('log.cache.removeFailed', { error: err }), 'error');
      } finally {
        btnRemoveSelected.disabled = false;
      }
    });
  }

  // Remove every downloaded patch (Settings).
  const btnClearCache = document.getElementById('btn-clear-patch-cache');
  if (btnClearCache) {
    btnClearCache.addEventListener('click', async () => {
      if (cachedPatchInfo.length === 0) return;
      const bytes = cachedPatchInfo.reduce((sum, e) => sum + e.size, 0);
      const mb = (bytes / 1048576).toFixed(1);
      const ok = await showConfirm(
        tPlural('tabPatcher.cache.clearConfirmMessage', cachedPatchInfo.length, { mb }),
        t('tabPatcher.cache.clearConfirmTitle')
      );
      if (!ok) return;

      btnClearCache.disabled = true;
      try {
        await withBusyLabel(btnClearCache, `<i class="fas fa-spinner fa-spin"></i> ${t('tabPatcher.cache.removing')}`, async () => {
          const [removed, freed] = await invoke("clear_patch_cache");
          log(msg('log.cache.clearedAll', { count: removed, mb: (freed / 1048576).toFixed(1) }), 'success');
          await refreshCachedPatches();
        });
      } catch (err) {
        log(msg('log.cache.clearFailed', { error: err }), 'error');
      } finally {
        btnClearCache.disabled = cachedPatchInfo.length === 0;
      }
    });
  }
}

// Fetches one patch variant from the remote patch library into the local
// cache, reporting live progress. Returns the absolute path on disk, which
// run_xdelta_patch accepts unchanged. A cached, verified copy returns almost
// immediately and emits no progress events.
async function downloadPatchVariant(config, patchKey, variant) {
  const slug = config.slug;
  if (!slug) throw msg('log.download.slugMissing');

  const totalMb = variant.size ? (variant.size / 1048576).toFixed(1) : "?";
  log(msg('log.download.notBundled', { packVersion: config.packVersion, patchVersion: config.patchVersion || "1.0" }));
  log(msg('log.download.variant', { variant: patchKey, mb: totalMb }));
  updateStatus(
    t('tabPatcher.status.preparingTitle'),
    t('tabPatcher.status.downloading', { patch: patchKey, total: totalMb }),
    '⬇️'
  );

  let unlisten = null;
  try {
    unlisten = await listen('patch-download-progress', (event) => {
      const p = event.payload || {};
      if (p.slug !== slug || p.variant !== patchKey) return;
      const total = p.total_bytes || variant.size || 0;
      const doneMb = (p.bytes_downloaded / 1048576).toFixed(1);
      if (total > 0) {
        const pct = Math.min(100, (p.bytes_downloaded / total) * 100);
        // The download spans the 55-75% band of the overall pipeline.
        // updateProgress writes the number straight into the label, so round it.
        updateProgress(Math.round(55 + (pct * 0.20)));
        updateStatus(
          t('tabPatcher.status.preparingTitle'),
          t('tabPatcher.status.downloadingProgress', { patch: patchKey, done: doneMb, total: totalMb, percent: pct.toFixed(0) }),
          '⬇️'
        );
      } else {
        updateStatus(
          t('tabPatcher.status.preparingTitle'),
          t('tabPatcher.status.downloadingProgressIndeterminate', { patch: patchKey, done: doneMb }),
          '⬇️'
        );
      }
    });

    const path = await invoke("ensure_patch_downloaded", {
      slug,
      variant: patchKey,
      url: variant.url,
      sha256: variant.sha256 || "",
      size: variant.size || 0
    });

    updateProgress(75);
    log(msg('log.download.ready', { path }), 'success');
    return path;
  } finally {
    if (unlisten) {
      try { unlisten(); } catch (_) {}
    }
  }
}

function updatePatchVersionsList(asVersion) {
  const patchSelect = document.getElementById('select-patch-version');
  if (!patchSelect) return;

  const matching = patchConfigs.filter(c => c.packVersion === asVersion)
    .sort((a, b) => {
      const verA = a.patchVersion || "1.0";
      const verB = b.patchVersion || "1.0";
      return verB.localeCompare(verA, undefined, { numeric: true, sensitivity: 'base' });
    });

  const previous = patchSelect.value;
  patchSelect.innerHTML = `<option value="latest">${t('tabPatcher.version.latestRecommended')}</option>`;
  matching.forEach(c => {
    const ver = c.patchVersion || "1.0";
    const opt = document.createElement('option');
    opt.value = ver;
    opt.innerText = `${t('tabPatcher.version.patchItem', { version: ver })} ${patchAvailabilityLabel(c)}`;
    patchSelect.appendChild(opt);
  });
  if (previous && Array.from(patchSelect.options).some(o => o.value === previous)) {
    patchSelect.value = previous;
  }

  updateSelectedPatchAvailability();
}

// Whether a config needs no download: either shipped in the installer, or
// already sitting in this user's patch cache.
function isPatchDownloaded(config) {
  if (!config) return false;
  const hasRemote = config.patches && Object.values(config.patches).some(v => v && typeof v === 'object' && v.url);
  if (!hasRemote) return true; // bundled with the app
  return isNeededVariantCached(config);
}

// A slug can be cached with only one of its variants, so "downloaded" has to
// mean the variant the current mode applies: encrypted for Marketplace,
// decrypted otherwise (the same choice the patch step makes).
function isNeededVariantCached(config) {
  const mode = document.querySelector('input[name="patch-mode"]:checked')?.value || 'global';
  const key = mode === 'marketplace' ? 'encrypted' : 'decrypted';
  const variant = config.patches && config.patches[key];
  if (!(variant && typeof variant === 'object' && variant.url)) return true; // nothing to download
  return !!(config.slug && cachedPatchVariants.get(config.slug)?.has(key));
}

function patchAvailabilityLabel(config) {
  const hasRemote = config.patches && Object.values(config.patches).some(v => v && typeof v === 'object' && v.url);
  if (!hasRemote) return '\u{1F4E6}';
  if (isNeededVariantCached(config)) return '\u2705';
  const bytes = Math.max(...Object.values(config.patches).map(v => (v && v.size) || 0));
  return bytes ? `\u2B07\uFE0F ${(bytes / 1048576).toFixed(0)} MB` : '\u2B07\uFE0F';
}

// Reflects the currently selected version in the availability hint and the
// per-version remove button.
function updateSelectedPatchAvailability() {
  const hint = document.getElementById('patch-availability-hint');
  const btnRemove = document.getElementById('btn-remove-selected-patch');
  if (!hint && !btnRemove) return;

  const asSel = document.getElementById('select-as-version');
  const patchSel = document.getElementById('select-patch-version');
  if (!asSel || !patchSel) return;

  const matching = patchConfigs.filter(c => c.packVersion === asSel.value)
    .sort((a, b) => (b.patchVersion || "1.0").localeCompare(a.patchVersion || "1.0", undefined, { numeric: true, sensitivity: 'base' }));
  const config = patchSel.value === 'latest'
    ? matching[0]
    : matching.find(c => (c.patchVersion || "1.0") === patchSel.value) || matching[0];

  if (hint) {
    if (!config) {
      delete hint.dataset.flash;
      hint.innerText = '';
    } else if (isPatchDownloaded(config)) {
      delete hint.dataset.flash;
      const bundled = !(config.patches && Object.values(config.patches).some(v => v && typeof v === 'object' && v.url));
      hint.innerHTML = bundled
        ? `<span style="color:#7ed17e;">${t('tabPatcher.version.includedWithApp')}</span>`
        : `<span style="color:#7ed17e;">${t('tabPatcher.version.downloadedOffline')}</span>`;
    } else {
      delete hint.dataset.flash;
      const bytes = Math.max(...Object.values(config.patches || {}).map(v => (v && v.size) || 0));
      const mb = bytes ? (bytes / 1048576).toFixed(0) : null;
      const text = mb
        ? t('tabPatcher.version.willBeDownloadedSize', { mb })
        : t('tabPatcher.version.willBeDownloaded');
      hint.innerHTML = `<span style="color:#e0b050;">${text}</span>`;
    }
  }

  if (btnRemove) {
    const removable = !!(config && config.slug && cachedPatchSlugs.has(config.slug));
    btnRemove.classList.toggle('hidden-group', !removable);
    btnRemove.dataset.slug = removable ? config.slug : '';
  }
}

// Refreshes the cached-patch set from disk, then repaints anything that shows
// download state.
async function refreshCachedPatches() {
  try {
    const cached = await invoke("list_cached_patches");
    cachedPatchSlugs = new Set(cached.map(c => c.slug));
    cachedPatchVariants = new Map(cached.map(c => [c.slug, new Set(c.variants)]));
    cachedPatchInfo = cached;
  } catch (err) {
    console.error("Failed to list downloaded patches", err);
    cachedPatchSlugs = new Set();
    cachedPatchVariants = new Map();
    cachedPatchInfo = [];
  }
  const asSel = document.getElementById('select-as-version');
  if (asSel && asSel.value) updatePatchVersionsList(asSel.value);
  renderDownloadedPatchesSettings();
}

// patch_config.json stores "v1.11.1" while the pack scanner reports "1.11.1",
// so versions must be normalised before any comparison.
// A trailing ".0" is dropped as well, so "1.11.0" and "v1.11" compare equal.
function normalizePackVersion(v) {
  return String(v ?? '').trim().replace(/^v/i, '').replace(/(\.0+)+$/, '');
}

function samePackVersion(a, b) {
  return normalizePackVersion(a) === normalizePackVersion(b);
}

// Stops the pipeline when the pack itself is fine but no patch has been
// published for its version. Not a failure: the user just has to wait.
class NoPatchForVersion extends Error {
  constructor(packVersion) {
    const logMessage = packVersion
      ? msg('log.resolve.noPatchForVersion', { version: packVersion })
      : msg('log.resolve.noPatchForInstalled');
    super(logMessage.toString());
    this.logMessage = logMessage;
    this.packVersion = packVersion || null;
  }
}

// Does a scanned pack look like the pack this patch config was built against?
// v1.11 and v1.11.1 share a logo hash, so file and directory counts are the
// only thing that separates them. Files tolerate a small delta (a user may have
// added a file); directories must match exactly.
function candidateMatchesConfig(candidate, config) {
  if (!candidate || !config) return false;
  const stats = config.stats || config.marketplace_pack_stats?.v1;
  if (!stats || (!stats.files && !stats.dirs)) return false;

  const fileMatch = stats.files && candidate.files_count > 0
    ? Math.abs(stats.files - candidate.files_count) <= 5
    : true;
  const dirMatch = stats.dirs && candidate.dirs_count > 0
    ? stats.dirs === candidate.dirs_count
    : true;
  return fileMatch && dirMatch;
}

// Best available description of the pack being patched. Prefer the scanner's
// own version string; fall back to a config whose stats match this pack.
function detectedVersionOf(candidate, fallbackConfig) {
  if (candidate && candidate.version && candidate.version !== 'Unknown') return candidate.version;
  const match = patchConfigs.find(c => candidateMatchesConfig(candidate, c));
  if (match) return match.packVersion;
  return (fallbackConfig && fallbackConfig.packVersion) || 'Unknown';

}

function resolvePatchConfig(selectionMode, detectedCandidate) {
  // Sort patchConfigs descending by packVersion and then by patchVersion
  const sortedConfigs = [...patchConfigs].sort((a, b) => {
    const verCompare = b.packVersion.localeCompare(a.packVersion, undefined, { numeric: true, sensitivity: 'base' });
    if (verCompare !== 0) return verCompare;
    const patchA = a.patchVersion || "1.0";
    const patchB = b.patchVersion || "1.0";
    return patchB.localeCompare(patchA, undefined, { numeric: true, sensitivity: 'base' });
  });

  if (selectionMode === 'auto') {
    if (detectedCandidate && typeof detectedCandidate === 'object') {
      // 1. Try to strictly match using stats and logo_hash
      const exactMatch = sortedConfigs.find(c => {
        const stats = c.stats || {};
        const valid = c.validation || {};
        
        // If the config requires validation, test it
        let hashMatch = true;
        if (valid.logo_hash && detectedCandidate.logo_hash) {
            hashMatch = valid.logo_hash === detectedCandidate.logo_hash;
        }

        let fileMatch = true;
        let dirMatch = true;
        if (stats.files && detectedCandidate.files_count > 0) {
            // Allow slight variance in files if user added a custom file, but mostly strict
            fileMatch = Math.abs(stats.files - detectedCandidate.files_count) <= 5;
        }
        if (stats.dirs && detectedCandidate.dirs_count > 0) {
            dirMatch = stats.dirs === detectedCandidate.dirs_count;
        }

        // If we have any of these fields to compare, and they match, it's a solid hit
        return (valid.logo_hash || stats.files) && hashMatch && fileMatch && dirMatch;
      });

      if (exactMatch) {
        log(msg('log.resolve.byStats', { packVersion: exactMatch.packVersion, patchVersion: exactMatch.patchVersion || "1.0" }));
        return exactMatch;
      }

      // 2. Fallback to version string
      if (detectedCandidate.version && detectedCandidate.version !== 'Unknown') {
        const verMatch = sortedConfigs.find(c => samePackVersion(c.packVersion, detectedCandidate.version));
        if (verMatch) {
          log(msg('log.resolve.byVersion', { packVersion: verMatch.packVersion, patchVersion: verMatch.patchVersion || "1.0" }));
          return verMatch;
        }
      }

      // 3. The pack names its own version and nothing is published for it.
      // Falling through to the newest patch here would only fail later with a
      // misleading "corrupted or modified" error.
      if (detectedCandidate.name_version) {
        throw new NoPatchForVersion(detectedCandidate.name_version);
      }
    } else if (typeof detectedCandidate === 'string' && detectedCandidate !== 'Unknown') {
      const verMatch = sortedConfigs.find(c => samePackVersion(c.packVersion, detectedCandidate));
      if (verMatch) {
        log(msg('log.resolve.byVersion', { packVersion: verMatch.packVersion, patchVersion: verMatch.patchVersion || "1.0" }));
        return verMatch;
      }
      throw new NoPatchForVersion(detectedCandidate);
    }
    // Default to the highest pack version config
    log(msg('log.resolve.noConfidentMatch', { packVersion: (sortedConfigs[0] || patchConfigs[0])?.packVersion }), 'warning');
    return sortedConfigs[0] || patchConfigs[0];
  } else {
    const selAsVal = document.getElementById('select-as-version').value;
    const selPatchVal = document.getElementById('select-patch-version').value;
    
    const matching = sortedConfigs.filter(c => c.packVersion === selAsVal);
    if (matching.length === 0) return sortedConfigs[0] || patchConfigs[0];
    
    if (selPatchVal === 'latest') {
      return matching[0];
    } else {
      return matching.find(c => (c.patchVersion || "1.0") === selPatchVal) || matching[0];
    }
  }
}

// Open a path in Explorer
async function openInExplorer(path) {
  if (!path) return;
  try {
    await invoke("open_in_explorer", { path });
  } catch (err) {
    log(msg('log.app.explorerFailed', { error: err }), 'warning');
  }
}

// File and Folder Picker bindings
async function bindPickers() {
  // Load default paths from Rust backend
  // Version Increaser / Decreaser Buttons
    const adjustVersion = async (inputId, index, amount) => {
    const el = document.getElementById(inputId);
    if (!el) return;
    let parts = el.value.split('.');
    while (parts.length <= index) parts.push('0');
    let val = parseInt(parts[index]);
    if (!isNaN(val)) {
      parts[index] = Math.max(0, val + amount);
      // Reset lower parts to 0 if increasing a higher part
      if (amount > 0) {
        for (let i = index + 1; i < parts.length; i++) {
          parts[i] = 0;
        }
      }
      el.value = parts.join('.');
      
      const packEl = document.getElementById('gen-pack-version');
      const patchEl = document.getElementById('gen-patch-version');
      try { await invoke("save_patch_versions", { packVersion: packEl ? packEl.value : "1.0", patchVersion: patchEl ? patchEl.value : "1.0" }); } catch(e) {}
    }
  };

  document.getElementById('btn-pack-major')?.addEventListener('click', () => adjustVersion('gen-pack-version', 0, 1));
  document.getElementById('btn-pack-minor')?.addEventListener('click', () => adjustVersion('gen-pack-version', 1, 1));
  document.getElementById('btn-pack-patch')?.addEventListener('click', () => adjustVersion('gen-pack-version', 2, 1));
  
  document.getElementById('btn-patch-major')?.addEventListener('click', () => adjustVersion('gen-patch-version', 0, 1));
  document.getElementById('btn-patch-minor')?.addEventListener('click', () => adjustVersion('gen-patch-version', 1, 1));
  
  try {
    defaultPaths = await invoke("get_default_paths");
    const edition = (defaultPaths.premium_cache || "").includes("MinecraftUWP")
      ? msg('log.app.editionUwp')
      : msg('log.app.editionGdk');
    log(msg('log.app.detectedInstall', { edition, premiumCache: defaultPaths.premium_cache, resourcePacks: defaultPaths.resource_packs }));
  } catch (err) {
    log(msg('log.app.detectInstallFailed', { error: err }), 'warning');
    defaultPaths = {};
  }

  const registerPicker = (btnId, inputId, isFolder, title, filter = "", defaultPath = "") => {
    const btn = document.getElementById(btnId);
    const input = document.getElementById(inputId);
    if (!btn || !input) return;
    
    // Pre-fill with default if available and input is empty
    if (defaultPath && !input.value) {
      input.value = defaultPath;
    }
    
    btn.addEventListener('click', async () => {
      try {
        let result = "";
        const currentPath = input.value || defaultPath || "";
        if (isFolder) {
          result = await invoke("select_directory", { title, defaultPath: currentPath });
        } else {
          result = await invoke("select_file", { title, filter, defaultPath: currentPath });
        }
        if (result) {
          input.value = result;
          log(msg('log.app.selected', { path: result }));
        }
      } catch (err) {
        log(msg('log.app.pickerError', { error: err }), 'error');
      }
    });
  };
  
  // --- Patcher: Zip mode file picker ---
  registerPicker('btn-browse-zip-input', 'zip-input-file', false,
    'Select Minecraft Resource Pack to Patch',
    'Minecraft Packs (*.zip *.mcpack)|*.zip;*.mcpack',
    defaultPaths.downloads || "");

  // --- Patcher Custom ---
  registerPicker('btn-browse-src', 'custom-src', true, 
    'Select Source Folder (Extract or ZIP)',
    '',
    defaultPaths.downloads || "");
  registerPicker('btn-browse-tgt', 'custom-tgt', false, 
    'Select Target Output File',
    'Minecraft Packs (*.mcpack *.zip)|*.mcpack;*.zip',
    defaultPaths.premium_cache || "");
  registerPicker('btn-browse-patch', 'custom-patch', false, 
    'Select VCDIFF Patch File',
    'Patch files (*.vcdiff)|*.vcdiff',
    defaultPaths.patches || "");
  
  // --- Utilities Pack ---
  registerPicker('btn-pack-src-browse', 'pack-src-folder', true, 
    'Select Folder to Compress',
    '',
    defaultPaths.downloads || "");
  registerPicker('btn-pack-dst-browse', 'pack-dst-file', false, 
    'Select Output Destination',
    'ZIP/MCPack (*.zip *.mcpack)|*.zip;*.mcpack',
    defaultPaths.downloads || "");
  
  // --- Utilities Extract ---
  registerPicker('btn-extract-src-browse', 'extract-src-file', false, 
    'Select Archive to Extract',
    'ZIP/MCPack (*.zip *.mcpack)|*.zip;*.mcpack',
    defaultPaths.downloads || "");
  registerPicker('btn-extract-dst-browse', 'extract-dst-folder', true, 
    'Select Extraction Destination',
    '',
    defaultPaths.downloads || "");

  // --- Utilities Gen Patch (V2 style: 4 folders) ---
  registerPicker('btn-gen-patched-browse', 'gen-patched-dir', true,
    'Select Your Modified/Patched Pack Folder (Target)',
    '',
    defaultPaths.resource_packs || "");
  registerPicker('btn-gen-decrypted-browse', 'gen-decrypted-dir', true,
    'Select Vanilla Decrypted Baseline Folder (Source)',
    '',
    defaultPaths.downloads || "");
  registerPicker('btn-gen-encrypted-browse', 'gen-encrypted-dir', true,
    'Select Vanilla Encrypted (Marketplace) Source Folder',
    '', 
    defaultPaths.premium_cache || "");
  registerPicker('btn-gen-output-browse', 'gen-output-dir', true,
    'Select Output Directory for .vcdiff files',
    '',
    defaultPaths.patches || "");

  // Pre-fill encrypted dir with premium_cache default
  const genEncInput = document.getElementById('gen-encrypted-dir');
  if (genEncInput && !genEncInput.value && defaultPaths.premium_cache) {
    genEncInput.value = defaultPaths.premium_cache;
  }

  // --- Utilities Standalone Brarchive Extractor ---
  registerPicker('btn-util-br-browse', 'util-br-folder', true,
    'Select Target Folder containing __brarchive directories',
    '',
    defaultPaths.downloads || "");
}

// Standalone Utilities setup
function setupUtilities() {
  document.getElementById('btn-run-pack').addEventListener('click', async () => {
    const src = document.getElementById('pack-src-folder').value;
    const dst = document.getElementById('pack-dst-file').value;
    
    if (!src || !dst) {
      await showAlert(t('tabUtils.pack.alerts.missingPaths'));
      return;
    }
    
    try {
      log(msg('log.utils.packStart', { path: src }));
      await invoke("pack_folder", { folderPath: src, outputZip: dst });
      log(msg('log.utils.packDone', { path: dst }), 'success');
      await showAlert(t('tabUtils.pack.alerts.success', { path: dst }));
    } catch (err) {
      log(msg('log.utils.packFailed', { error: err }), 'error');
      await showAlert(t('tabUtils.pack.alerts.failed', { error: err }));
    }
  });

  document.getElementById('btn-run-extract').addEventListener('click', async () => {
    const src = document.getElementById('extract-src-file').value;
    const dst = document.getElementById('extract-dst-folder').value;
    
    if (!src || !dst) {
      await showAlert(t('tabUtils.extract.alerts.missingPaths'));
      return;
    }
    
    try {
      log(msg('log.utils.extractStart', { src, dst }));
      await invoke("extract_archive", { zipPath: src, outputDir: dst });
      log(msg('log.utils.extractDone', { path: dst }), 'success');
      await showAlert(t('tabUtils.extract.alerts.success'));
    } catch (err) {
      log(msg('log.utils.extractFailed', { error: err }), 'error');
      await showAlert(t('tabUtils.extract.alerts.failed', { error: err }));
    }
  });

  // ---- V2-style Create Patch ----
  document.getElementById('btn-run-gen-patch').addEventListener('click', async () => {
    const patchedDir   = document.getElementById('gen-patched-dir').value;
    const decryptedDir = document.getElementById('gen-decrypted-dir').value;
    const encryptedDir = document.getElementById('gen-encrypted-dir').value;
    const outputDir    = document.getElementById('gen-output-dir').value;
    const packVer      = document.getElementById('gen-pack-version').value.trim() || "1.10.1";
    const patchVer     = document.getElementById('gen-patch-version').value.trim() || "1.0";
    const injectManifest = document.getElementById('gen-inject-manifest').checked;
    const encryptTarget = document.getElementById('gen-encrypt-target').checked;

    if (!patchedDir || !decryptedDir || !encryptedDir || !outputDir) {
      await showAlert(t('tabUtils.genpatch.alerts.missingPaths'));
      return;
    }

    const gLog = document.getElementById('genpatch-logs');
    const gLog_fn = (m, type = 'info') => logTo('genpatch-logs', m, type);

    resetLog(gLog, msg('log.placeholder.genpatchStarting'));
    document.getElementById('btn-run-gen-patch').disabled = true;

    try {
      gLog_fn(msg('log.genpatch.versions', { pack: packVer, patch: patchVer }));

      if (injectManifest) {
          // identitySourceDir always points at the Encrypted Dir, not whichever
          // folder is being written to: a working Decrypted/Patched Dir can
          // easily already carry a custom manifest from a previous run (and
          // so no longer have the pack's real purchased uuid at all), while
          // the raw Encrypted Dir — untouched Marketplace cache — always does.
          gLog_fn(msg('log.genpatch.injectingBaseline'));
          try {
              await invoke("inject_custom_manifest_to_target", { targetDir: decryptedDir, packVer: "", patchVer: "", identitySourceDir: encryptedDir });
          } catch (e) {
              gLog_fn(msg('log.genpatch.injectBaselineFailed', { error: e }), "warning");
          }

          gLog_fn(msg('log.genpatch.injectingVersioned'));
          try {
              await invoke("inject_custom_manifest_to_target", { targetDir: patchedDir, packVer: packVer, patchVer: patchVer, identitySourceDir: encryptedDir });
          } catch (e) {
              gLog_fn(msg('log.genpatch.injectVersionedFailed', { error: e }), "warning");
          }
      }

      // Step 1: Compress the Encrypted (Marketplace) source → encrypted.vcdiff source
      gLog_fn(msg('log.genpatch.step1', { path: encryptedDir }));
      const encZip = outputDir + "/_temp_source_enc.zip";
      await invoke("pack_folder", { folderPath: encryptedDir, outputZip: encZip });
      gLog_fn(msg('log.genpatch.encSourceReady'));

      // Step 2: Compress the Decrypted (vanilla) source → decrypted.vcdiff source
      // Excludes the same 4 files normalize_extracted_pack strips from a real
      // end-user's pack before applying decrypted.vcdiff (see the zip-mode
      // patch flow below). Without this, a Decrypted Dir that still has any
      // of these (a genuine pre-decrypted copy usually does) bakes them into
      // the patch's expected source, which then can never byte-match what
      // normalize_extracted_pack produces at apply time — xdelta3 fails with
      // a target window checksum mismatch on every single application.
      gLog_fn(msg('log.genpatch.step2', { path: decryptedDir }));
      const decZip = outputDir + "/_temp_source_dec.zip";
      const NORMALIZED_AWAY_FILES = ["contents.json", "signatures.json", "splashes.json", "sounds.json"];
      await invoke("pack_folder", { folderPath: decryptedDir, outputZip: decZip, excludeNames: NORMALIZED_AWAY_FILES });
      gLog_fn(msg('log.genpatch.decSourceReady'));

      // Step 3: Compress patched (target) folder → target ZIP
      gLog_fn(msg('log.genpatch.step3', { path: patchedDir }));
      const tgtZip = outputDir + "/_temp_target.zip";
      const tempTargetDir = outputDir + "/_temp_target_dir";

      // A copy left over from a failed run would be merged into the new one.
      await invoke("delete_folders", { folders: [tempTargetDir] });
      await invoke("prepare_patch_target", {
        rtxDir: patchedDir,
        tempTargetDir: tempTargetDir
      });

      // With encryption there are two targets, both made from the temp copy
      // only. The decrypted patch leads to the plain pack with its .brarchive
      // files built; the encrypted patch to that same pack, encrypted.
      if (encryptTarget) {
        await invoke("build_patch_target_archives", { targetDir: tempTargetDir });
      }

      await invoke("pack_folder", { folderPath: tempTargetDir, outputZip: tgtZip });
      gLog_fn(msg('log.genpatch.targetReady'));

      // The manifest is final by now, which matters: the encrypted pack's
      // signatures.json holds the manifest hash.
      const encTgtZip = encryptTarget ? outputDir + "/_temp_target_enc.zip" : tgtZip;
      if (encryptTarget) {
        await invoke("encrypt_patch_target", { targetDir: tempTargetDir });
        await invoke("pack_folder", { folderPath: tempTargetDir, outputZip: encTgtZip });
        gLog_fn(msg('log.genpatch.encTargetReady'));
      }

      // Step 4: Generate both patches
      gLog_fn(msg('log.genpatch.step4'));

      const folderName = `Actions & Stuff for RTX ${packVer} V${patchVer}`;
      const finalOutputDir = outputDir + "/" + folderName;

      const encPatch = finalOutputDir + "/encrypted.vcdiff";
      const decPatch = finalOutputDir + "/decrypted.vcdiff";

      gLog_fn(msg('log.genpatch.encodingEnc'));
      await invoke("generate_xdelta_patch", { sourceFile: encZip, targetFile: encTgtZip, patchFile: encPatch });
      gLog_fn(msg('log.genpatch.encCreated'));

      gLog_fn(msg('log.genpatch.encodingDec'));
      await invoke("generate_xdelta_patch", { sourceFile: decZip, targetFile: tgtZip, patchFile: decPatch });
      gLog_fn(msg('log.genpatch.decCreated'));

      // Calculate patch stats from the encrypted directory
      gLog_fn(msg('log.genpatch.calcStats', { path: encryptedDir }));
      let patchStats = null;
      try {
          patchStats = await invoke("calculate_patch_stats", { folderPath: encryptedDir });
          gLog_fn(msg('log.genpatch.statsDone', { files: patchStats.files, dirs: patchStats.dirs }));
      } catch (err) {
          gLog_fn(msg('log.genpatch.statsFailed', { error: err }), "warning");
      }

      // Generate patch_config.json
      const configPath = finalOutputDir + "/patch_config.json";
      const configData = {
          packVersion: `v${packVer}`,
          patchVersion: patchVer,
          marketplace_pack_stats: {
              v1: { 
                  files: patchStats ? patchStats.files : 11653, 
                  dirs: patchStats ? patchStats.dirs : 159 
              }
          },
          validation: {
              logo_hash: patchStats ? patchStats.logo_hash : "d4d088d108cd635116215134ad40e97272f9fbe17ead8a03ba4155b1f58fecd4",
              has_lang_file: patchStats ? patchStats.has_lang_file : true
          }
      };
      await invoke("write_text_file", { path: configPath, content: JSON.stringify(configData, null, 4) });
      gLog_fn(msg('log.genpatch.configCreated'));

      // Clean temp zips and folders
      await invoke("delete_folders", { folders: [encZip, decZip, tgtZip, encTgtZip, tempTargetDir] });

      gLog_fn(msg('log.genpatch.allDone', { path: finalOutputDir }), 'success');
      gLog_fn(msg('log.genpatch.summary', { pack: packVer, patch: patchVer }), 'success');

      // Save current patch version persistently
      try {
        await invoke("save_patch_versions", { packVersion: packVer, patchVersion: patchVer });
      } catch (err) {
        console.error("Failed to save patch version:", err);
      }

      // The patch exists on disk and is good from here on, so nothing below is
      // allowed to report the creation itself as failed.
      lastCreatedPatchFolder = finalOutputDir;
      const btnPublish = document.getElementById('btn-publish-last-patch');
      if (btnPublish) btnPublish.classList.remove('hidden-group');

      const wantsPublish = document.getElementById('gen-publish-library');
      if (wantsPublish && wantsPublish.checked) {
        try {
          await publishPatchToLibrary(finalOutputDir, { packVer, patchVer });
        } catch (err) {
          gLog_fn(msg('log.publish.failedPatchFine', { error: err }), 'warning');
        }
      }

      // Open output folder in Explorer
      try { await invoke("open_in_explorer", { path: finalOutputDir }); } catch (_) {}

    } catch (err) {
      gLog_fn(msg('log.genpatch.failed', { error: err }), 'error');
      await showAlert(t('tabUtils.genpatch.alerts.failed', { error: err }));
    } finally {
      document.getElementById('btn-run-gen-patch').disabled = false;
    }
  });

  // Copy / Clear genpatch log
  const btnCopyGenpatch = document.getElementById('btn-copy-genpatch-log');
  if (btnCopyGenpatch) btnCopyGenpatch.addEventListener('click', () => copyLogsFromEl('genpatch-logs', 'btn-copy-genpatch-log'));
  const btnClearGenpatch = document.getElementById('btn-clear-genpatch-log');
  if (btnClearGenpatch) btnClearGenpatch.addEventListener('click', () => {
    resetLog(document.getElementById('genpatch-logs'), msg('log.placeholder.genpatchReady'));
  });

  // Brarchive tool: extract switch, experimental geometry-rename switch, own console
  const brExtract = document.getElementById('util-br-extract');
  const brRename = document.getElementById('util-br-rename');
  const brRunBtn = document.getElementById('btn-run-util-br');
  const brResults = document.getElementById('util-br-results');
  const brLog = (m, type = 'info') => logTo('brarchive-logs', m, type);

  const updateBrButton = () => {
    const ex = brExtract.checked, rn = brRename.checked;
    brRunBtn.textContent = ex && rn ? t('tabUtils.brarchive.runBtn.extractAndRename')
      : rn ? t('tabUtils.brarchive.runBtn.renameOnly')
      : ex ? t('tabUtils.brarchive.extractBtn')
      : t('tabUtils.brarchive.runBtn.nothing');
    brRunBtn.disabled = !ex && !rn;
  };
  try {
    brExtract.checked = localStorage.getItem('brTool.extract') !== '0';
    brRename.checked = localStorage.getItem('brTool.rename') === '1';
  } catch (_) {}
  [brExtract, brRename].forEach(el => el.addEventListener('change', () => {
    try {
      localStorage.setItem('brTool.extract', brExtract.checked ? '1' : '0');
      localStorage.setItem('brTool.rename', brRename.checked ? '1' : '0');
    } catch (_) {}
    updateBrButton();
  }));
  updateBrButton();
  // The label is chosen here rather than by a data-i18n key, so it has to follow a language switch itself.
  onLocaleChange(() => { if (!brRunBtn.disabled || (!brExtract.checked && !brRename.checked)) updateBrButton(); });

  document.getElementById('btn-copy-br-log').addEventListener('click', () => copyLogsFromEl('brarchive-logs', 'btn-copy-br-log'));
  document.getElementById('btn-clear-br-log').addEventListener('click', () => {
    resetLog(document.getElementById('brarchive-logs'), msg('log.placeholder.brarchiveCleared'));
  });

  const renderBrResults = (packs) => {
    brResults.innerHTML = '';
    const renamed = packs.filter(p => p.renamed > 0);
    if (!renamed.length) { brResults.classList.add('hidden-group'); return; }
    brResults.classList.remove('hidden-group');
    for (const p of renamed) {
      const s = p.summary;
      const box = document.createElement('div');
      box.className = 'status-hint';
      box.style.cssText = 'padding: 10px; border-radius: 8px; margin-bottom: 8px; background: rgba(255,255,255,0.04);';
      const title = document.createElement('div');
      title.style.cssText = 'font-weight: 600; color: #fff; margin-bottom: 4px; word-break: break-all;';
      title.textContent = p.pack;
      const lines = [
        t('tabUtils.brarchive.results.renamed', { renamed: p.renamed, files: p.files_changed }),
        p.errors.length
          ? tPlural('tabUtils.brarchive.results.validationErrors', p.errors.length, { errors: p.errors.join('; ') })
          : t('tabUtils.brarchive.results.validationPassed'),
        t('tabUtils.brarchive.results.review', { review: s.review, conflicts: s.role_conflicts, medium: s.orphan_medium }),
        t('tabUtils.brarchive.results.incomplete', { suffixes: s.unresolved_suffix, kept: s.kept_original }),
      ];
      box.appendChild(title);
      lines.forEach((l, i) => {
        const d = document.createElement('div');
        d.textContent = l;
        if (i === 1) d.style.color = p.errors.length ? 'var(--color-danger)' : 'var(--color-success)';
        if (i === 2 && s.review) d.style.color = 'var(--color-warning)';
        box.appendChild(d);
      });
      const btn = document.createElement('button');
      btn.className = 'btn btn-secondary btn-xs';
      btn.style.marginTop = '6px';
      btn.textContent = t('tabUtils.brarchive.results.openChecklist');
      btn.addEventListener('click', () => invoke('open_in_explorer', { path: p.checklist_path }).catch(e => brLog(`${e}`, 'error')));
      box.appendChild(btn);
      brResults.appendChild(box);
    }
  };

  brRunBtn.addEventListener('click', async () => {
    const folder = document.getElementById('util-br-folder').value;
    if (!folder) {
      await showAlert(t('tabUtils.brarchive.alerts.missingFolder'));
      return;
    }
    const extract = brExtract.checked, rename = brRename.checked;
    if (rename) {
      const ok = await showModal(
        t('tabUtils.brarchive.renameConfirm.message'),
        { title: t('tabUtils.brarchive.renameConfirm.title'), confirm: true, okText: t('tabUtils.brarchive.renameConfirm.okBtn'), cancelText: t('common.cancel') });
      if (!ok) return;
    }

    brRunBtn.disabled = true;
    const label = brRunBtn.textContent;
    brRunBtn.textContent = t('tabUtils.brarchive.runBtn.working');
    brResults.classList.add('hidden-group');
    const t0 = performance.now();
    try {
      const res = await invoke("run_brarchive_tool", { workspace: folder, extract, rename });
      const secs = ((performance.now() - t0) / 1000).toFixed(1);
      renderBrResults(res.packs || []);
      const errs = (res.packs || []).reduce((n, p) => n + p.errors.length, 0);
      brLog(msg('log.brarchive.finished', { secs }), errs ? 'warning' : 'success');
      if (rename && !(res.packs || []).some(p => p.renamed > 0) && !(res.packs || []).some(p => p.already_renamed)) {
        brLog(msg('log.brarchive.nothingRenamed'), 'warning');
      }
    } catch (err) {
      brLog(msg('log.brarchive.failed', { error: err }), 'error');
      await showAlert(t('tabUtils.brarchive.alerts.toolFailed', { error: err }));
    } finally {
      brRunBtn.textContent = label;
      updateBrButton();
    }
  });

  // Utilities dropdown and sidebar subtab navigation
  const toolSelect = document.getElementById('utils-tool-select');
  const utilsDropdown = document.getElementById('nav-utils-dropdown');
  const utilsToggle = utilsDropdown ? utilsDropdown.querySelector('.nav-dropdown-toggle') : null;
  const subtabs = utilsDropdown ? utilsDropdown.querySelectorAll('.nav-subtab') : [];

  function activateUtilityCard(utilName) {
    if (toolSelect) {
      toolSelect.value = utilName;
      toolSelect.dispatchEvent(new Event('change'));
    }
    subtabs.forEach(st => {
      if (st.dataset.util === utilName) {
        st.classList.add('active');
      } else {
        st.classList.remove('active');
      }
    });
    if (utilsDropdown) {
      utilsDropdown.classList.add('open');
    }
    if (utilsToggle) {
      utilsToggle.classList.add('active');
    }
  }

  if (toolSelect) {
    toolSelect.addEventListener('change', (e) => {
      const selected = e.target.value;
      const cards = ['pack', 'extract', 'genpatch', 'brarchive'];
      cards.forEach(card => {
        const cardEl = document.getElementById(`util-card-${card}`);
        if (cardEl) {
          if (card === selected) {
            cardEl.classList.remove('hidden-group');
          } else {
            cardEl.classList.add('hidden-group');
          }
        }
      });

      subtabs.forEach(st => {
        if (st.dataset.util === selected) {
          st.classList.add('active');
        } else {
          st.classList.remove('active');
        }
      });
    });
  }

  if (utilsToggle && utilsDropdown) {
    utilsToggle.addEventListener('click', (e) => {
      const isOpen = utilsDropdown.classList.toggle('open');
      if (isOpen) {
        const activeSubtab = utilsDropdown.querySelector('.nav-subtab.active');
        if (!activeSubtab && subtabs.length > 0) {
          activateUtilityCard(subtabs[0].dataset.util);
        }
      }
    });
  }

  subtabs.forEach(subtab => {
    subtab.addEventListener('click', (e) => {
      e.stopPropagation();
      
      tabs.forEach(t => t.classList.remove('active'));
      
      const utilName = subtab.dataset.util;
      activateUtilityCard(utilName);
      
      tabContents.forEach(tc => tc.classList.remove('active'));
      const targetTab = document.getElementById('tab-utils');
      if (targetTab) {
        targetTab.classList.add('active');
      }
    });
  });
}

// Options.txt direct editor setup
async function loadOptionsProfiles() {
  try {
    optionsProfiles = await invoke("get_options_paths");
    log(msg('log.options.profilesFound', {
      count: optionsProfiles.length,
      labels: optionsProfiles.map(p => p.label).join(", ") || msg('log.options.none'),
    }));
    const select = document.getElementById('options-file-select');
    select.innerHTML = `<option value="" data-i18n="tabRtxSettings.chooseProfile">${t('tabRtxSettings.chooseProfile')}</option>`;

    optionsProfiles.forEach((profile, index) => {
      const opt = document.createElement('option');
      opt.value = profile.path;
      opt.innerText = profile.label;
      select.appendChild(opt);
    });
    
    select.addEventListener('change', async (e) => {
      selectedOptionsPath = e.target.value;
      if (selectedOptionsPath) {
        await loadOptionsData(selectedOptionsPath);
      } else {
        document.getElementById('rtx-settings-grid').innerHTML = `<div class="placeholder-text" data-i18n="tabRtxSettings.placeholder">${t('tabRtxSettings.placeholder')}</div>`;
        document.getElementById('btn-save-settings').disabled = true;
        document.getElementById('btn-best-settings').disabled = true;
      }
    });
  } catch (err) {
    log(msg('log.options.profilesFailed', { error: err }), 'error');
  }
}

async function loadOptionsData(path) {
  try {
    log(msg('log.options.reading', { path }));
    const data = await invoke("read_options", { path });
    
    const rtxKeys = {
      'gfx_raytracing': { labelKey: 'tabRtxSettings.fields.raytracing', type: 'bool' },
      'gfx_upscaling': { labelKey: 'tabRtxSettings.fields.upscaling', type: 'bool' },
      'raytracing_viewdistance': { labelKey: 'tabRtxSettings.fields.viewDistance', type: 'number' },
      'gfx_max_framerate': { labelKey: 'tabRtxSettings.fields.maxFramerate', type: 'number' },
      'gfx_vsync': { labelKey: 'tabRtxSettings.fields.vsync', type: 'bool' },
      'enable_dithering_blocks': { labelKey: 'tabRtxSettings.fields.blockDithering', type: 'bool' },
      'enable_dithering_mobs': { labelKey: 'tabRtxSettings.fields.mobDithering', type: 'bool' }
    };
    
    const grid = document.getElementById('rtx-settings-grid');
    grid.innerHTML = '';
    
    Object.keys(rtxKeys).forEach(key => {
      const cfg = rtxKeys[key];
      const val = data[key] !== undefined ? data[key] : '0';
      
      const field = document.createElement('div');
      field.className = 'option-field';
      
      const labelSpan = document.createElement('span');
      labelSpan.className = 'option-name';
      labelSpan.dataset.i18n = cfg.labelKey;
      labelSpan.innerText = t(cfg.labelKey);
      field.appendChild(labelSpan);
      
      const controlDiv = document.createElement('div');
      controlDiv.className = 'option-control';
      
      if (cfg.type === 'bool') {
        const toggle = document.createElement('label');
        toggle.className = 'mc-toggle';
        
        const inp = document.createElement('input');
        inp.type = 'checkbox';
        inp.dataset.key = key;
        inp.checked = (val == '1');
        
        const slider = document.createElement('span');
        slider.className = 'mc-slider';
        
        toggle.appendChild(inp);
        toggle.appendChild(slider);
        
        controlDiv.appendChild(toggle);
      } else if (cfg.type === 'percent' || cfg.type === 'number') {
        const inp = document.createElement('input');
        inp.type = 'number';
        inp.dataset.key = key;
        inp.value = val;
        controlDiv.appendChild(inp);
      }
      
      field.appendChild(controlDiv);
      grid.appendChild(field);
    });
    
    document.getElementById('btn-save-settings').disabled = false;
    document.getElementById('btn-best-settings').disabled = false;
  } catch (err) {
    log(msg('log.options.readFailed', { error: err }), 'error');
  }
}

document.getElementById('btn-save-settings').addEventListener('click', async () => {
  if (!selectedOptionsPath) return;
  
  const controls = document.querySelectorAll('.option-control select, .option-control input');
  const changes = {};
  controls.forEach(ctrl => {
    if (ctrl.type === 'checkbox') {
      changes[ctrl.dataset.key] = ctrl.checked ? '1' : '0';
    } else {
      changes[ctrl.dataset.key] = ctrl.value;
    }
  });
  
  try {
    log(msg('log.options.saving'));
    await invoke("write_options", { path: selectedOptionsPath, changes });
    log(msg('log.options.saved'), 'success');
    await showAlert(t('tabRtxSettings.alerts.saveSuccess'));
  } catch (err) {
    log(msg('log.options.saveFailed', { error: err }), 'error');
    await showAlert(t('tabRtxSettings.alerts.saveError', { error: err }));
  }
});

document.getElementById('btn-best-settings').addEventListener('click', async () => {
  const rt = document.querySelector('input[data-key="gfx_raytracing"]');
  const dlss = document.querySelector('input[data-key="gfx_upscaling"]');
  const vd = document.querySelector('input[data-key="raytracing_viewdistance"]');
  const db = document.querySelector('input[data-key="enable_dithering_blocks"]');
  const dm = document.querySelector('input[data-key="enable_dithering_mobs"]');
  
  if (rt) rt.checked = true;
  if (dlss) dlss.checked = true;
  if (vd) vd.value = "12";
  if (db) db.checked = false;
  if (dm) dm.checked = false;
  
  log(msg('log.options.bestLoaded'), "info");
  await showAlert(t('tabRtxSettings.alerts.bestLoaded'));
});


// Cleaner panel setup
let cleanablePacksPaths = [];

// Paths the user has ticked for deletion. Everything found starts selected.
let cleanSelectedPaths = new Set();

function cleanerSelectedList() {
  return cleanablePacksPaths.filter(p => cleanSelectedPaths.has(p));
}

function updateCleanerButtons() {
  const selected = cleanerSelectedList().length;
  const total = cleanablePacksPaths.length;
  const btnSelected = document.getElementById('btn-run-cleaner');
  const btnAll = document.getElementById('btn-clean-delete-all');

  if (btnSelected) {
    btnSelected.disabled = selected === 0;
    btnSelected.innerText = selected > 0
      ? tPlural('tabCleaner.actions.deleteSelectedCount', selected)
      : t('tabCleaner.actions.deleteSelected');
  }
  if (btnAll) {
    btnAll.disabled = total === 0;
    btnAll.innerText = total > 0
      ? tPlural('tabCleaner.actions.deleteAllCount', total)
      : t('tabCleaner.actions.deleteAll');
  }

  ['btn-clean-select-all', 'btn-clean-select-none'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.classList.toggle('hidden-group', total === 0);
  });

  const countTag = document.getElementById('clean-results-count');
  if (countTag) {
    countTag.innerText = total === 0
      ? t('tabCleaner.results.noneFound')
      : t('tabCleaner.results.selectedOfTotal', { selected, total });
  }
}

function renderCleanerResults() {
  const list = document.getElementById('clean-results-list');
  if (!list) return;
  list.innerHTML = '';

  if (cleanablePacksPaths.length === 0) {
    list.innerHTML = `<div class="placeholder-text" data-i18n="tabCleaner.results.clean">${t('tabCleaner.results.clean')}</div>`;
    updateCleanerButtons();
    return;
  }

  cleanablePacksPaths.forEach(p => {
    const parts = p.split(/[\\/]/);
    const name = parts[parts.length - 1] || p;

    const item = document.createElement('div');
    item.className = 'clean-item';
    item.style.cssText = 'display:flex;align-items:center;gap:10px;';

    const box = document.createElement('input');
    box.type = 'checkbox';
    box.checked = cleanSelectedPaths.has(p);
    box.style.cssText = 'flex:0 0 auto;cursor:pointer;';
    box.addEventListener('change', () => {
      if (box.checked) cleanSelectedPaths.add(p); else cleanSelectedPaths.delete(p);
      updateCleanerButtons();
    });

    const text = document.createElement('div');
    text.style.cssText = 'min-width:0;flex:1;cursor:pointer;';
    text.innerHTML = `<div style="font-size:0.85rem;color:#ffffff;">${name}</div>`;
    const pathSpan = document.createElement('div');
    pathSpan.className = 'clean-item-path';
    pathSpan.style.maxWidth = '100%';
    pathSpan.innerText = p;
    pathSpan.title = p;
    text.appendChild(pathSpan);
    // Clicking the row toggles it, which is easier to hit than the checkbox.
    text.addEventListener('click', () => { box.checked = !box.checked; box.dispatchEvent(new Event('change')); });

    item.appendChild(box);
    item.appendChild(text);
    list.appendChild(item);
  });

  updateCleanerButtons();
}

async function runCleanerScan({ quiet = false } = {}) {
  if (!quiet) log(msg('log.cleaner.scanning'));
  cleanablePacksPaths = await invoke("get_cleanable_packs");
  cleanSelectedPaths = new Set(cleanablePacksPaths); // default to everything selected
  renderCleanerResults();
  if (!quiet) {
    log(cleanablePacksPaths.length === 0
      ? msg('log.cleaner.scanClean')
      : msg('log.cleaner.scanFound', { count: cleanablePacksPaths.length }));
  }
}

function setCleanProgress(done, total, label) {
  const wrap = document.getElementById('clean-progress-wrap');
  const fill = document.getElementById('clean-progress-fill');
  const text = document.getElementById('clean-progress-text');
  if (!wrap || !fill || !text) return;
  wrap.classList.remove('hidden-group');
  fill.style.width = `${total ? Math.round((done / total) * 100) : 0}%`;
  text.innerText = label;
}

// Deletes one folder at a time so the bar reflects real progress. delete_folders
// takes a list, but a single call gives no feedback until every folder is gone,
// and these can hold thousands of files each.
async function deleteCleanerPaths(paths, description) {
  const confirmDelete = await showConfirm(
    tPlural('tabCleaner.confirm.message', paths.length, { description }),
    t('tabCleaner.confirm.title')
  );
  if (!confirmDelete) return;

  const buttons = ['btn-scan-cleaner', 'btn-run-cleaner', 'btn-clean-delete-all', 'btn-clean-select-all', 'btn-clean-select-none']
    .map(id => document.getElementById(id)).filter(Boolean);
  buttons.forEach(b => { b.disabled = true; });

  let deleted = 0;
  let failed = 0;
  try {
    log(msg('log.cleaner.deleting', { count: paths.length }));
    setCleanProgress(0, paths.length, tPlural('tabCleaner.progress.preparing', paths.length));

    for (let i = 0; i < paths.length; i++) {
      const name = paths[i].split(/[\\/]/).pop() || paths[i];
      setCleanProgress(i, paths.length, t('tabCleaner.progress.deleting', { current: i + 1, total: paths.length, name }));
      try {
        const count = await invoke("delete_folders", { folders: [paths[i]] });
        if (count > 0) { deleted++; } else { failed++; log(msg('log.cleaner.couldNotDelete', { path: paths[i] }), 'warning'); }
      } catch (err) {
        failed++;
        log(msg('log.cleaner.deleteFailed', { path: paths[i], error: err }), 'error');
      }
    }

    const doneLabel = failed
      ? tPlural('tabCleaner.progress.doneWithFailures', deleted, { failed })
      : tPlural('tabCleaner.progress.done', deleted);
    setCleanProgress(paths.length, paths.length, doneLabel);
    log(failed
      ? msg('log.cleaner.summaryWithFailures', { deleted, failed })
      : msg('log.cleaner.summary', { deleted }), failed ? 'warning' : 'success');
  } finally {
    buttons.forEach(b => { b.disabled = false; });
    // Re-scan so the list reflects what is actually left, including anything
    // that could not be removed because Minecraft still had it open.
    await runCleanerScan({ quiet: true });
    setTimeout(() => {
      const wrap = document.getElementById('clean-progress-wrap');
      if (wrap) wrap.classList.add('hidden-group');
    }, 4000);
  }
}

document.getElementById('btn-scan-cleaner').addEventListener('click', async () => {
  try {
    await runCleanerScan();
  } catch (err) {
    log(msg('log.cleaner.scanFailed', { error: err }), 'error');
  }
});

document.getElementById('btn-clean-select-all').addEventListener('click', () => {
  cleanSelectedPaths = new Set(cleanablePacksPaths);
  renderCleanerResults();
});

document.getElementById('btn-clean-select-none').addEventListener('click', () => {
  cleanSelectedPaths.clear();
  renderCleanerResults();
});

document.getElementById('btn-clean-delete-all').addEventListener('click', async () => {
  if (cleanablePacksPaths.length === 0) return;
  await deleteCleanerPaths([...cleanablePacksPaths], t('tabCleaner.confirm.descAll'));
});

document.getElementById('btn-run-cleaner').addEventListener('click', async () => {
  const selected = cleanerSelectedList();
  if (selected.length === 0) return;
  await deleteCleanerPaths(selected, t('tabCleaner.confirm.descSelected'));
});

// CORE PATCHER PIPELINE
let finalPatchedPath = "";

document.getElementById('btn-start-patch').addEventListener('click', async () => {
  const mode = document.querySelector('input[name="patch-mode"]:checked').value;
  const selectionMode = document.getElementById('version-selection-mode').value;
  const cleanOld = document.getElementById('chk-clean-old').checked;

  // Reset UI
  clearConsole();
  resetSteps();
  document.getElementById('progress-actions-container').classList.add('hidden-group');
  document.getElementById('btn-install-pack').classList.add('hidden-group');
  document.getElementById('btn-copy-log-large').classList.add('hidden-group');
  document.getElementById('btn-start-patch').disabled = true;
  finalPatchedPath = "";

  // Swap panels: hide controls, show progress
  document.querySelector('.controls-panel').classList.add('hidden-group');
  document.querySelector('.progress-panel').classList.remove('hidden-group');
  
  log(msg('log.patcher.start', { mode }));
  log(msg('log.patcher.selectionMode', { mode: selectionMode }));
  log(msg('log.patcher.cleanupOption', { state: msg(cleanOld ? 'log.patcher.enabled' : 'log.patcher.disabled') }));

  try {
    let sourceZipPath = "";
    let patchConfigToUse = null;
    // The pack we actually chose to patch, and the folder picked if the user
    // had to browse manually. Both feed the compression step below.
    let selectedCandidate = null;
    let browsedPackPath = "";
    
    // ----------------------------------------
    // STEP 0: SCAN & VERIFY
    // ----------------------------------------
    updateStepState(0, 'active');
    updateStatus(t('tabPatcher.status.verifyingTitle'), t('tabPatcher.status.verifyingText'), '🔍');
    updateProgress(10);
    
    if (mode === 'marketplace') {
      log(msg('log.patcher.scanningMarketplace'));
      let expectedStats = { expectedLogoHash: null, expectedHasLangFile: null, validStatsList: null };
      if (selectionMode === 'manual') {
        const asVer = document.getElementById('select-as-version').value;
        const ptVer = document.getElementById('select-patch-version').value;
        // Goes through the resolver so "Latest" in the patch list maps to a real entry.
        const selected = resolvePatchConfig('manual', null);
        if (selected) {
          expectedStats.expectedLogoHash = selected.validation?.logo_hash || null;
          expectedStats.expectedHasLangFile = selected.validation?.has_lang_file || null;
          
          let files = selected.marketplace_pack_stats?.v1?.files || selected.stats?.files || 0;
          let dirs = selected.marketplace_pack_stats?.v1?.dirs || selected.stats?.dirs || 0;
          if (files > 0 && dirs > 0) {
            expectedStats.validStatsList = [{ files, dirs, version: selected.packVersion || null, is_latest: true }];
          }
        }
      } else {
        const sortedConfigs = [...patchConfigs].sort((a, b) => b.packVersion.localeCompare(a.packVersion, undefined, { numeric: true, sensitivity: 'base' }));
        if (sortedConfigs.length > 0) {
          expectedStats.expectedLogoHash = sortedConfigs[0].validation?.logo_hash || null;
          expectedStats.expectedHasLangFile = sortedConfigs[0].validation?.has_lang_file || null;
          
          let statsList = sortedConfigs.map((c, i) => {
            let files = c.marketplace_pack_stats?.v1?.files || c.stats?.files || 0;
            let dirs = c.marketplace_pack_stats?.v1?.dirs || c.stats?.dirs || 0;
            return {
              files,
              dirs,
              version: c.packVersion || null,
              is_latest: (i === 0)
            };
          }).filter(s => s.files > 0 && s.dirs > 0);
          
          if (statsList.length > 0) {
            expectedStats.validStatsList = statsList;
          }
        }
      }
      let candidates;
      try {
        candidates = await invoke("scan_marketplace_packs", expectedStats);
      } catch (err) {
        // The scanner found Actions & Stuff installed, but none of the patches
        // it was asked about fits that pack.
        const noPatch = /^NO_PATCH_FOR_PACK:(.*)$/.exec(String(err));
        if (!noPatch) throw err;
        const installed = noPatch[1];
        if (installed && patchConfigs.some(c => samePackVersion(c.packVersion, installed))) {
          throw msg('log.patcher.errors.installedMismatch', { version: installed });
        }
        throw new NoPatchForVersion(installed);
      }
      log(msg('log.patcher.candidatesFound', { count: candidates.length }));

      candidates.forEach((cand, idx) => {
        log(msg('log.patcher.candidate', { index: idx + 1 }));
        log(msg('log.patcher.candFolder', { value: cand.folder_name }));
        log(msg('log.patcher.candPath', { value: cand.path }));
        log(msg('log.patcher.candVersion', { value: cand.version }));
        log(msg('log.patcher.candContents', { files: cand.files_count, dirs: cand.dirs_count }));
        log(msg('log.patcher.candScore', { value: cand.score }));
      });

      if (candidates.length === 0) {
        log(msg('log.patcher.noMarketplacePack'));
        const browsePath = await invoke("select_directory", { title: "Browse and select your Actions & Stuff pack folder manually" });
        if (!browsePath) {
          throw msg('log.patcher.errors.browseCancelled');
        }
        log(msg('log.patcher.manualBrowsed', { path: browsePath }));
        browsedPackPath = browsePath;
        patchConfigToUse = resolvePatchConfig(selectionMode, null);
      } else {
        // In Auto mode the scanner's ranking decides. In Manual mode the user
        // has already named a version, so patch the pack that actually matches
        // it - picking the top-ranked pack regardless would silently apply the
        // patch to a different version and fail xdelta's source checksum.
        let best = candidates[0];
        if (selectionMode === 'manual') {
          const wanted = resolvePatchConfig(selectionMode, null);
          const match = wanted && candidates.find(c => candidateMatchesConfig(c, wanted));
          if (match) {
            best = match;
          } else if (wanted) {
            log(msg('log.patcher.noCandidateMatches', { version: wanted.packVersion }), 'warning');
          }
        }
        selectedCandidate = best;

        log(msg('log.patcher.selectedCandidate'));
        log(msg('log.patcher.selPath', { path: best.path }));
        log(msg('log.patcher.selVersion', { version: best.version }));
        log(msg('log.patcher.selComplexity', { files: best.files_count, dirs: best.dirs_count }));

        patchConfigToUse = resolvePatchConfig(selectionMode, best);

        if (selectionMode === 'auto' && patchConfigToUse && patchConfigToUse.stats) {
          const stats = patchConfigToUse.stats;
          let fileMatch = true;
          let dirMatch = true;
          if (stats.files && best.files_count > 0) {
              fileMatch = Math.abs(stats.files - best.files_count) <= 5;
          }
          if (stats.dirs && best.dirs_count > 0) {
              dirMatch = stats.dirs === best.dirs_count;
          }
          if (!fileMatch || !dirMatch) {
              throw msg('log.patcher.errors.validationFailed', {
                expectedFiles: stats.files, expectedDirs: stats.dirs, files: best.files_count, dirs: best.dirs_count,
              });
          }
        }

        // Warn when the manually chosen patch does not match the pack we are
        // about to patch. This compares against the detected pack: the previous
        // version overwrote the detected value with the selected one, so the
        // two sides were always equal and the check never fired.
        const detectedVersion = detectedVersionOf(best, patchConfigToUse);

        if (selectionMode === 'manual' && patchConfigToUse &&
            normalizePackVersion(patchConfigToUse.packVersion) !== normalizePackVersion(detectedVersion)) {
          log(msg('log.patcher.versionMismatch', { selected: patchConfigToUse.packVersion, detected: detectedVersion }), 'warning');
          const proceed = await showConfirm(
            t('tabPatcher.versionMismatch.message', { selected: patchConfigToUse.packVersion, detected: detectedVersion }),
            t('tabPatcher.versionMismatch.title')
          );
          if (!proceed) {
            throw msg('log.patcher.errors.versionMismatchAborted');
          }
        }
      }
      
      updateStepState(0, 'completed');
      
      // STEP 1: COMPRESSION / NORMALIZATION
      updateStepState(1, 'active');
      
      // Must follow the candidate actually selected above, not the top-ranked
      // one, or Manual mode would compress a different pack than it patches.
      // browsedPackPath covers the manual-browse fallback, whose chosen folder
      // was previously discarded in favour of an unrelated custom-src field.
      const sourcePackPath = selectedCandidate
        ? selectedCandidate.path
        : (browsedPackPath || document.getElementById('custom-src').value);
      const tempRoot = defaultPaths.temp ? defaultPaths.temp.replace(/\\/g, "/") : ".";
      const baseName = sourcePackPath.split(/[\\/]/).pop() || "source";
      const zipOut = `${tempRoot}/${baseName}_vanilla.zip`;
      let targetFolder = sourcePackPath;

      updateStatus(t('tabPatcher.status.compressingTitle'), t('tabPatcher.status.compressingText'), '📦');
      updateProgress(25);

      log(msg('log.patcher.zipStart'));
      log(msg('log.patcher.field.compressing', { path: targetFolder }));
      log(msg('log.patcher.field.outputZip', { path: zipOut }));
      await invoke("pack_folder", { folderPath: targetFolder, outputZip: zipOut });
      log(msg('log.patcher.sourceZipCreated', { path: zipOut }));

      sourceZipPath = zipOut;
      updateStepState(1, 'completed');
      
    } else if (mode === 'zip') {
      // Use pre-selected file from the Zip mode file picker
      let selectedZip = document.getElementById('zip-input-file') ? document.getElementById('zip-input-file').value : '';
      if (!selectedZip) {
        log(msg('log.patcher.noFilePreselected'));
        selectedZip = await invoke("select_file", {
          title: "Select Minecraft Resource Pack to Patch",
          filter: "Minecraft Packs (*.zip *.mcpack)|*.zip;*.mcpack"
        });
      }
      if (!selectedZip) {
        throw msg('log.patcher.errors.noFileSelected');
      }
      log(msg('log.patcher.selectedArchive', { path: selectedZip }));
      updateStepState(0, 'completed');
      
      updateStepState(1, 'active');
      updateStatus(t('tabPatcher.status.extractingTitle'), t('tabPatcher.status.extractingText'), '⚙️');
      updateProgress(20);
      
      const tempRoot = defaultPaths.temp ? defaultPaths.temp.replace(/\\/g, "/") : ".";
      const baseName = selectedZip.split(/[\\/]/).pop() || "pack";
      
      const tempExtract = `${tempRoot}/${baseName}_extracted`;
      log(msg('log.patcher.extractingZip'));
      log(msg('log.patcher.field.sourceZip', { path: selectedZip }));
      log(msg('log.patcher.field.targetDir', { path: tempExtract }));
      await invoke("extract_archive", { zipPath: selectedZip, outputDir: tempExtract });
      log(msg('log.patcher.extractDone'));

      // Resolved before the slow normalise/compress steps, so an archive that
      // nothing is published for stops here. Auto mode goes by the version
      // the pack names itself; without one it falls back to the newest patch.
      let zipPackVersion = null;
      if (selectionMode === 'auto') {
        try {
          zipPackVersion = await invoke("detect_pack_version", { folder: tempExtract });
        } catch (_) {}
        log(msg('log.patcher.archiveVersion', { version: zipPackVersion || msg('log.patcher.notFound') }));
      }
      try {
        patchConfigToUse = resolvePatchConfig(selectionMode, zipPackVersion);
      } catch (err) {
        try { await invoke("delete_folders", { folders: [tempExtract] }); } catch (_) {}
        throw err;
      }

      log(msg('log.patcher.normalizing'));
      log(msg('log.patcher.field.targetDir', { path: tempExtract }));
      await invoke("normalize_extracted_pack", { extractDir: tempExtract });
      log(msg('log.patcher.normalizeDone'));

      const normalizedZip = `${tempRoot}/${baseName}_normalized.zip`;
      updateStatus(t('tabPatcher.status.compressingNormalizedTitle'), t('tabPatcher.status.compressingNormalizedText'), '⚙️');
      updateProgress(35);
      log(msg('log.patcher.recompressing'));
      log(msg('log.patcher.field.compressing', { path: tempExtract }));
      log(msg('log.patcher.field.outputZip', { path: normalizedZip }));
      await invoke("pack_folder", { folderPath: tempExtract, outputZip: normalizedZip });
      log(msg('log.patcher.recompressDone'));

      log(msg('log.patcher.deletingTemp', { path: tempExtract }));
      await invoke("delete_folders", { folders: [tempExtract] });
      log(msg('log.patcher.tempCleaned'));
      
      sourceZipPath = normalizedZip;

      updateStepState(1, 'completed');
      
    } else if (mode === 'custom') {
      const src = document.getElementById('custom-src').value;
      const tgt = document.getElementById('custom-tgt').value;
      const patch = document.getElementById('custom-patch').value;
      
      if (!src || !tgt || !patch) {
        throw msg('log.patcher.errors.customMissingPaths');
      }

      log(msg('log.patcher.customParams'));
      log(msg('log.patcher.field.source', { path: src }));
      log(msg('log.patcher.field.target', { path: tgt }));
      log(msg('log.patcher.field.patch', { path: patch }));
      
      updateStepState(0, 'completed');
      updateStepState(1, 'active');
      
      if (src.endsWith('.zip') || src.endsWith('.mcpack')) {
        updateStatus(t('tabPatcher.status.copyingSourceTitle'), t('tabPatcher.status.copyingSourceText'), '📦');
        updateProgress(30);
        log(msg('log.patcher.sourceIsZip', { path: src }));
        sourceZipPath = src;
      } else {
        const tempRoot = defaultPaths.temp ? defaultPaths.temp.replace(/\\/g, "/") : ".";
        const baseName = src.split(/[\\/]/).pop() || "custom";
        updateStatus(t('tabPatcher.status.compressingCustomTitle'), t('tabPatcher.status.compressingCustomText'), '📦');
        updateProgress(30);
        const customZip = `${tempRoot}/${baseName}_custom_source.zip`;
        log(msg('log.patcher.sourceIsFolder', { zip: customZip, src }));
        await invoke("pack_folder", { folderPath: src, outputZip: customZip });
        sourceZipPath = customZip;
      }
      
      updateStepState(1, 'completed');
    }
    
    // STEP 2: CLEAN REMNANTS
    updateStepState(2, 'active');
    if (cleanOld) {
      updateStatus(t('tabPatcher.status.cleaningTitle'), t('tabPatcher.status.cleaningText'), '🧹');
      updateProgress(45);
      log(msg('log.patcher.scanningRemnants'));
      const cleanable = await invoke("get_cleanable_packs");
      if (cleanable.length > 0) {
        log(msg('log.patcher.remnantsFound', { count: cleanable.length }));
        cleanable.forEach(p => log(msg('log.patcher.remnant', { path: p })));
        log(msg('log.patcher.deletingRemnants'));
        const cleaned = await invoke("delete_folders", { folders: cleanable });
        log(msg('log.patcher.remnantsRemoved', { count: cleaned }));
      } else {
        log(msg('log.patcher.noRemnants'));
      }
    } else {
      log(msg('log.patcher.remnantsSkipped'));
    }
    updateStepState(2, 'completed');
    
    // STEP 3: ENSURE THE PATCH FILE IS AVAILABLE (download it if it is remote)
    updateStepState(3, 'active');
    updateStatus(t('tabPatcher.status.preparingTitle'), t('tabPatcher.status.locatingPatch'), '📦');
    updateProgress(55);

    let patchFilePath = "";
    let finalOutputPath = "";
    let usedPatchSlug = null;

    if (mode === 'custom') {
      patchFilePath = document.getElementById('custom-patch').value;
      finalOutputPath = document.getElementById('custom-tgt').value;
    } else {
      if (!patchConfigToUse) {
        throw msg('log.patcher.errors.noConfig');
      }

      const isEncrypted = mode === 'marketplace';
      const patchKey = isEncrypted ? 'encrypted' : 'decrypted';
      const variant = patchConfigToUse.patches && patchConfigToUse.patches[patchKey];

      if (variant && typeof variant === 'object' && variant.url) {
        // Remote entry from the patch library: fetch it into the local cache.
        // run_xdelta_patch takes the absolute cache path unchanged.
        patchFilePath = await downloadPatchVariant(patchConfigToUse, patchKey, variant);
        usedPatchSlug = patchConfigToUse.slug || null;
      } else if (variant) {
        // Explicit path override in a patch_config.json.
        patchFilePath = variant;
      } else {
        // Bundled patch shipped inside the installer.
        patchFilePath = `assets/Patches/${patchConfigToUse.folder_name}/${isEncrypted ? 'encrypted.vcdiff' : 'decrypted.vcdiff'}`;
      }

      const sourcePackPath = sourceZipPath;
      const idx = sourcePackPath.lastIndexOf('.');
      finalOutputPath = idx !== -1
        ? `${sourcePackPath.substring(0, idx)}_RTX_Patched.zip`
        : `${sourcePackPath}_RTX_Patched.zip`;
    }

    updateStepState(3, 'completed');

    // STEP 4: APPLY RTX PATCH
    updateStepState(4, 'active');
    updateStatus(t('tabPatcher.status.applyingTitle'), t('tabPatcher.status.applyingText'), '⚡');
    updateProgress(80);

    log(msg('log.patcher.applying'));
    log(msg('log.patcher.field.patch', { path: patchFilePath }));
    log(msg('log.patcher.field.source', { path: sourceZipPath }));
    log(msg('log.patcher.field.output', { path: finalOutputPath }));
    log(msg('log.patcher.runningXdelta'));

    await invoke("run_xdelta_patch", {
      sourceZip: sourceZipPath,
      patchFile: patchFilePath,
      outputFile: finalOutputPath
    });

    log(msg('log.patcher.applyDone'), 'success');
    updateStepState(4, 'completed');

    // Housekeeping only: never allowed to fail the run, since the patch is
    // already applied by this point.
    try {
      if (appSettings.autoCleanPatchCache && usedPatchSlug) {
        const removed = await invoke("prune_patch_cache", { keepSlug: usedPatchSlug });
        if (removed > 0) log(msg('log.cache.pruned', { count: removed }));
      }
      await refreshCachedPatches();
    } catch (err) {
      log(msg('log.cache.tidyFailed', { error: err }), 'warning');
    }

    // Clean intermediate zip
    if (mode === 'marketplace' || mode === 'zip' || (mode === 'custom' && !document.getElementById('custom-src').value.endsWith('.zip'))) {
      log(msg('log.patcher.cleaningTempZip', { path: sourceZipPath }));
      await invoke("delete_folders", { folders: [sourceZipPath] });
      log(msg('log.patcher.tempZipCleaned'));
    }
    
    // STEP 5: IMPORT PACK
    updateStepState(5, 'active');
    updateStatus(t('tabPatcher.status.doneTitle'), t('tabPatcher.status.doneText'), '🎉');
    updateProgress(100);
    
    finalPatchedPath = finalOutputPath;
    document.getElementById('progress-actions-container').classList.remove('hidden-group');
    document.getElementById('btn-install-pack').classList.remove('hidden-group');
    document.getElementById('btn-copy-log-large').classList.remove('hidden-group');
    log(msg('log.patcher.success'), 'success');

  } catch (err) {
    const noPatch = err instanceof NoPatchForVersion;
    if (noPatch) {
      log(err.logMessage, 'warning');
      updateStatus(
        t('tabPatcher.status.noPatchTitle'),
        err.packVersion
          ? t('tabPatcher.status.noPatchForVersion', { version: err.packVersion })
          : t('tabPatcher.status.noPatchForInstalled'),
        '🕓'
      );
    } else {
      log(msg('log.patcher.pipelineFailure', { error: err }), 'error');
      updateStatus(t('tabPatcher.status.failedTitle'), t('tabPatcher.status.failedText'), '❌');
    }
    updateProgress(0);
    document.getElementById('progress-actions-container').classList.remove('hidden-group');
    document.getElementById('btn-install-pack').classList.add('hidden-group');
    document.getElementById('btn-copy-log-large').classList.remove('hidden-group');
    // A missing patch is nothing to report as a bug.
    document.getElementById('btn-report-bug-quick').classList.toggle('hidden-group', noPatch);
  } finally {
    document.getElementById('btn-start-patch').disabled = false;
  }
});

document.getElementById('btn-install-pack').addEventListener('click', async () => {
  if (!finalPatchedPath) return;
  const btn = document.getElementById('btn-install-pack');
  const originalText = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${t('tabPatcher.installing')}`;

  try {
    log(msg('log.patcher.launchingInstaller', { path: finalPatchedPath }));
    const actualMcpack = await invoke("install_mcpack", { outputFile: finalPatchedPath });
    log(msg('log.patcher.installed', { path: actualMcpack }), 'success');
    updateStepState(5, 'completed');
    btn.classList.add('hidden-group');
  } catch (err) {
    log(msg('log.patcher.installFailed', { error: err }), 'error');
    btn.disabled = false;
    btn.innerHTML = originalText;
  }
});

// Advanced Mode Switch Listener
document.getElementById('chk-advanced-mode').addEventListener('change', (e) => {
  const isChecked = e.target.checked;
  document.querySelectorAll('.advanced-only').forEach(el => {
    if (isChecked) {
      el.classList.remove('hidden-group');
    } else {
      el.classList.add('hidden-group');
    }
  });

  const zipLabel = document.getElementById('mode-zip-label');
  const zipInput = document.getElementById('radio-mode-zip');
  const customLabel = document.getElementById('mode-custom-label');
  const customInput = document.getElementById('radio-mode-custom');

  if (isChecked) {
    zipLabel.classList.remove('disabled-mode');
    zipLabel.removeAttribute('title');
    zipInput.disabled = false;

    customLabel.classList.remove('disabled-mode');
    customLabel.removeAttribute('title');
    customInput.disabled = false;
  } else {
    zipLabel.classList.add('disabled-mode');
    zipLabel.setAttribute('title', 'Enable Advanced Mode to use this feature');
    zipInput.disabled = true;

    customLabel.classList.add('disabled-mode');
    customLabel.setAttribute('title', 'Enable Advanced Mode to use this feature');
    customInput.disabled = true;

    const activeRadio = document.querySelector('input[name="patch-mode"]:checked');
    if (activeRadio && (activeRadio.value === 'custom' || activeRadio.value === 'zip')) {
      const marketplaceRadio = document.querySelector('input[name="patch-mode"][value="marketplace"]');
      if (marketplaceRadio) {
        marketplaceRadio.checked = true;
        marketplaceRadio.dispatchEvent(new Event('change'));
      }
    }
  }
  checkForUpdates();
});

// Back to Selection Button
document.getElementById('btn-patch-back').addEventListener('click', () => {
  document.querySelector('.progress-panel').classList.add('hidden-group');
  document.querySelector('.controls-panel').classList.remove('hidden-group');
  document.getElementById('btn-report-bug-quick').classList.add('hidden-group');
  updateStatus(t('tabPatcher.status.readyTitle'), t('tabPatcher.status.readySubtitle'), '💤');
  updateProgress(0);
  resetSteps();
});

// Quick Report Bug Button
document.getElementById('btn-report-bug-quick').addEventListener('click', () => {
  // Navigate to Support Tab
  document.querySelector('.nav-tab[data-tab="support"]').click();
  // Scroll to Bug Report section
  document.getElementById('bug-discord-name').scrollIntoView({ behavior: 'smooth', block: 'center' });
  document.getElementById('bug-discord-name').focus();
});

// Copy Console Log
const btnCopyLog = document.getElementById('btn-copy-log');
if (btnCopyLog) btnCopyLog.addEventListener('click', () => copyLogsFromEl('console-logs', 'btn-copy-log'));
const btnCopyLogLarge = document.getElementById('btn-copy-log-large');
if (btnCopyLogLarge) btnCopyLogLarge.addEventListener('click', () => copyLogsFromEl('console-logs', 'btn-copy-log-large'));
document.getElementById('btn-clear-console').addEventListener('click', clearConsole);

function parseVersion(verStr) {
  const isBeta = verStr.endsWith('_b') || verStr.endsWith('-b') || verStr.endsWith('-0');
  const isAlpha = verStr.endsWith('_a') || verStr.endsWith('-a') || verStr.endsWith('-1');
  const cleanVer = isBeta || isAlpha ? verStr.slice(0, -2) : verStr;
  const parts = cleanVer.split('.').map(Number);
  
  let relType = 'stable';
  if (isBeta) relType = 'beta';
  else if (isAlpha) relType = 'alpha';
  
  return {
    major: isNaN(parts[0]) ? 0 : parts[0],
    minor: isNaN(parts[1]) ? 0 : parts[1],
    patch: isNaN(parts[2]) ? 0 : parts[2],
    relType: relType
  };
}

function formatVersion(parsed) {
  let suffix = '';
  if (parsed.relType === 'beta') suffix = '_b';
  else if (parsed.relType === 'alpha') suffix = '_a';
  return `${parsed.major}.${parsed.minor}.${parsed.patch}${suffix}`;
}

// =====================================================================
// RELEASE BUILDER
// =====================================================================
function setupReleaseBuilder() {
  const buildLog = document.getElementById('build-logs');
  const bLog = (m, type = 'info') => logTo('build-logs', m, type);

  // Load current version from tauri.conf.json via a simple read
  const versionBadge = document.getElementById('app-version-badge');
  const relVerInput = document.getElementById('rel-app-version');
  const relHint = document.getElementById('rel-version-hint');
  const selReleaseType = document.getElementById('select-release-type');

  const updateVerInputs = (parsed) => {
    if (relVerInput) {
      relVerInput.value = formatVersion(parsed);
    }
    if (selReleaseType) {
      selReleaseType.value = parsed.relType;
    }
  };

  if (versionBadge && relVerInput) {
    const currentVer = versionBadge.innerText.replace('v', '').trim();
    const parsed = parseVersion(currentVer);
    updateVerInputs(parsed);
    if (relHint) relHint.innerText = t('tabRelease.versionEditor.current', { version: versionBadge.innerText });
  }

  // Increment buttons listeners
  document.getElementById('btn-inc-major')?.addEventListener('click', () => {
    if (!relVerInput) return;
    const parsed = parseVersion(relVerInput.value);
    parsed.major += 1;
    parsed.minor = 0;
    parsed.patch = 0;
    updateVerInputs(parsed);
  });

  document.getElementById('btn-inc-minor')?.addEventListener('click', () => {
    if (!relVerInput) return;
    const parsed = parseVersion(relVerInput.value);
    parsed.minor += 1;
    parsed.patch = 0;
    updateVerInputs(parsed);
  });

  document.getElementById('btn-inc-patch')?.addEventListener('click', () => {
    if (!relVerInput) return;
    const parsed = parseVersion(relVerInput.value);
    parsed.patch += 1;
    updateVerInputs(parsed);
  });

  // Release type select listener
  selReleaseType?.addEventListener('change', (e) => {
    if (!relVerInput) return;
    const parsed = parseVersion(relVerInput.value);
    parsed.relType = e.target.value;
    updateVerInputs(parsed);
  });

  // Apply version button — writes to tauri.conf.json
  const btnApplyVer = document.getElementById('btn-apply-version');
  if (btnApplyVer) {
    btnApplyVer.addEventListener('click', async () => {
      const newVer = relVerInput ? relVerInput.value.trim() : '';
      if (!newVer) { await showAlert(t('tabRelease.alerts.enterVersion')); return; }
      try {
        await invoke("update_app_version", { version: newVer });
        if (relHint) relHint.innerText = t('tabRelease.versionEditor.currentSaved', { version: `v${newVer}` });
        if (versionBadge) versionBadge.innerText = `v${newVer}`;
      } catch (err) {
        bLog(msg('log.release.updateVersionFailed', { error: err }), 'error');
        await showAlert(t('tabRelease.alerts.updateVersionFailed', { error: err }));
      }
    });
  }

  const btnBuildAll = document.getElementById('btn-build-all');
  const btnBuildInstallers = document.getElementById('btn-build-installers');
  const btnBuildPortable = document.getElementById('btn-build-portable');

  async function handleBuild(buildType) {
    const currentVersion = document.getElementById('rel-app-version').value;
    if (currentVersion) {
      try {
        const exists = await invoke("check_build_exists", { version: currentVersion });
        if (exists) {
          const result = await showModal(
            t('tabRelease.confirmOverwrite.message', { version: currentVersion }),
            {
              title: t('tabRelease.confirmOverwrite.title'),
              confirm: true,
              okText: t('tabRelease.confirmOverwrite.overwriteBtn'),
              cancelText: t('common.cancel')
            }
          );
          if (!result) {
            return;
          }
        }
      } catch (e) {
        console.warn("Failed to check if build exists:", e);
      }
    }

    const buildLog = document.getElementById('build-logs');
    resetLog(buildLog, msg('log.placeholder.buildStarting', { type: buildType }));
    
    if (btnBuildAll) btnBuildAll.disabled = true;
    if (btnBuildInstallers) btnBuildInstallers.disabled = true;
    if (btnBuildPortable) btnBuildPortable.disabled = true;

    try {
      await invoke("run_release_build", { buildType: buildType });
    } catch (err) {
      buildLog.appendChild(makeLogLine(msg('log.release.buildFailed', { error: err }), 'error', { timestamp: false }));
      await showAlert(t('tabRelease.alerts.buildFailed', { error: err }));
    } finally {
      if (btnBuildAll) btnBuildAll.disabled = false;
      if (btnBuildInstallers) btnBuildInstallers.disabled = false;
      if (btnBuildPortable) btnBuildPortable.disabled = false;
    }
  }

  if (btnBuildAll) {
    btnBuildAll.addEventListener('click', () => handleBuild("all"));
  }
  if (btnBuildInstallers) {
    btnBuildInstallers.addEventListener('click', () => handleBuild("installers_only"));
  }
  if (btnBuildPortable) {
    btnBuildPortable.addEventListener('click', () => handleBuild("portable_only"));
  }

  // Open bundle folder
  const btnOpenBundle = document.getElementById('btn-open-bundle-folder');
  if (btnOpenBundle) {
    btnOpenBundle.addEventListener('click', async () => {
      try {
        await invoke("open_project_dir", { name: "bundle" });
      } catch (err) {
        log(msg('log.release.openBundleFailed', { error: err }), 'error');
        await showAlert(t('tabRelease.alerts.openBundleFailed', { error: err }));
      }
    });
  }

  // Open patches folder
  const btnOpenPatches = document.getElementById('btn-open-patches-folder');
  if (btnOpenPatches) {
    btnOpenPatches.addEventListener('click', async () => {
      try {
        await invoke("open_project_dir", { name: "patches" });
      } catch (err) {
        log(msg('log.release.openPatchesFailed', { error: err }), 'error');
        await showAlert(t('tabRelease.alerts.openPatchesFailed', { error: err }));
      }
    });
  }

  // "What's the difference?" (pseudonymous vs anonymous) links
  ['btn-pseudonymous-info', 'btn-pseudonymous-info-modal'].forEach((id) => {
    const btn = document.getElementById(id);
    if (btn) {
      btn.addEventListener('click', async () => {
        try {
          await invoke("open_url", { url: "https://en.wikipedia.org/wiki/Pseudonymization" });
        } catch (e) {
          console.warn("Failed to open URL", e);
        }
      });
    }
  });

  // Support Links
  const btnChaosDiscord = document.getElementById('btn-chaos-discord');
  if (btnChaosDiscord) {
    btnChaosDiscord.addEventListener('click', async () => {
      try {
        await invoke("open_url", { url: "https://discord.gg/YrMMmN2kc7" }); // Chaos dev server
      } catch (e) {
        console.warn("Failed to open URL", e);
      }
    });
  }

  const btnBetterrtxDiscord = document.getElementById('btn-betterrtx-discord');
  if (btnBetterrtxDiscord) {
    btnBetterrtxDiscord.addEventListener('click', async () => {
      try {
        await invoke("open_url", { url: "https://discord.gg/HPP6J4qFPu" }); // Better RTX
      } catch (e) {
        console.warn("Failed to open URL", e);
      }
    });
  }

  // Copy/Clear build log
  const btnCopyBuild = document.getElementById('btn-copy-build-log');
  if (btnCopyBuild) btnCopyBuild.addEventListener('click', () => copyLogsFromEl('build-logs', 'btn-copy-build-log'));
  const btnClearBuild = document.getElementById('btn-clear-build-log');
  if (btnClearBuild) btnClearBuild.addEventListener('click', () => {
    resetLog(buildLog, msg('log.placeholder.buildReady'));
  });
}

// --- Telemetry & Privacy (DSGVO) -------------------------------------------
async function setupTelemetry() {
  const consentToggle = document.getElementById('set-telemetry-consent');
  const statusEl = document.getElementById('telemetry-settings-status');
  const modal = document.getElementById('telemetry-consent-modal');

  let state = null;
  try {
    state = await invoke('get_telemetry_state');
  } catch (e) {
    console.error('Failed to load telemetry state', e);
    return;
  }

  const applyConsent = async (consent) => {
    try {
      state = await invoke('set_telemetry_consent', { consent });
      if (consentToggle) consentToggle.checked = consent;
      if (consent) {
        // Fire the ping (self-guards: consent + only uploads if something changed).
        const res = await invoke('submit_hardware_ping');
        if (res && res.sent) log(msg('log.app.hardwarePingSent'));
      }
    } catch (e) {
      console.error('Telemetry consent update failed', e);
    }
  };

  // First run: no decision recorded yet -> show the consent modal.
  if (state.consent === null || state.consent === undefined) {
    if (modal) {
      modal.classList.remove('hidden-group');
      document.getElementById('btn-consent-accept')?.addEventListener('click', async () => {
        modal.classList.add('hidden-group');
        await applyConsent(true);
      });
      document.getElementById('btn-consent-decline')?.addEventListener('click', async () => {
        modal.classList.add('hidden-group');
        await applyConsent(false);
      });
    }
  } else if (state.consent === true) {
    if (consentToggle) consentToggle.checked = true;
    // Re-check silently on every start; only actually uploads if something changed.
    invoke('submit_hardware_ping').catch(() => {});
  }

  consentToggle?.addEventListener('change', async (e) => {
    await applyConsent(e.target.checked);
    if (statusEl) statusEl.innerText = e.target.checked
      ? t('tabSupport.telemetry.enabledStatus')
      : t('tabSupport.telemetry.disabledStatus');
  });

  document.getElementById('btn-view-telemetry-payload')?.addEventListener('click', async () => {
    try {
      await invoke('open_diagnostics_folder');
    } catch (e) {
      showModal(t('tabSupport.telemetry.openDiagnosticsError', { error: e }), { title: t('tabSupport.telemetry.errorTitle') });
    }
  });

  document.getElementById('btn-delete-telemetry-data')?.addEventListener('click', async () => {
    const confirmed = await showModal(
      t('tabSupport.telemetry.deleteConfirmMessage'),
      {
        title: t('tabSupport.telemetry.deleteConfirmTitle'),
        confirm: true,
        okText: t('tabSupport.telemetry.deleteBtn'),
        cancelText: t('common.cancel')
      }
    );
    if (!confirmed) return;
    try {
      await invoke('telemetry_delete_my_data');
      if (statusEl) statusEl.innerText = t('tabSupport.telemetry.deleteSuccess');
    } catch (e) {
      if (statusEl) statusEl.innerText = t('tabSupport.telemetry.deleteError', { error: e });
    }
  });
}

// Prepares the Minecraft content log for a bug report, showing step-by-step
// instructions (and re-enabling the submit button) if Minecraft needs to
// generate a usable one first (logging was off, log too old/small/large,
// etc). Returns the zip path on success, or null if the caller should stop
// submitting — instructions were already shown and the button re-enabled.
// Shared by the general Bug Reporter and the one-click Known Issue reporter,
// since both need the exact same "walk the user through fixing this" flow.
async function prepareContentLogOrInstruct(statusEl, btnSubmit) {
  statusEl.innerHTML = `${t('tabSupport.contentLog.checking')} <span class='status-spinner'>⏳</span>`;
  const clRes = await invoke('prepare_content_log');
  if (clRes.status === 'ok') {
    return clRes.zip_path;
  }

  // Each situation only explains why the log is unusable; the steps to fix it
  // are the same every time, so they are one string translated once.
  let reason;
  if (clRes.status === 'logging_was_off') {
    reason = t('tabSupport.contentLog.reasons.loggingOff');
  } else if (clRes.status === 'log_too_small') {
    reason = t('tabSupport.contentLog.reasons.tooSmall', { size: clRes.log_size_mb });
  } else if (clRes.status === 'log_too_old') {
    reason = t('tabSupport.contentLog.reasons.tooOld');
  } else if (clRes.status === 'log_too_large') {
    reason = t('tabSupport.contentLog.reasons.tooLarge', { size: clRes.log_size_mb });
  } else { // no_log
    reason = t('tabSupport.contentLog.reasons.noLog');
  }
  const instruction = `${reason}\n\n${t('tabSupport.contentLog.steps')}`;
  statusEl.innerText = t('tabSupport.contentLog.notSentStatus');
  statusEl.className = "status-hint";
  btnSubmit.disabled = false;
  await showModal(instruction, { title: t('tabSupport.contentLog.modalTitle') });
  return null;
}

async function setupBugReporter() {
  const btnSubmit = document.getElementById('btn-submit-bug');
  if (!btnSubmit) return;

  btnSubmit.addEventListener('click', async () => {
    const discordName = document.getElementById('bug-discord-name').value.trim();
    if (!discordName) {
      showAlert(t('tabSupport.bugReport.alerts.enterDiscord'));
      return;
    }

    if (discordName.includes(' ')) {
      showAlert(t('tabSupport.bugReport.alerts.noSpacesDiscord'));
      return;
    }

    const categories = Array.from(document.querySelectorAll('.bug-category:checked')).map(c => c.value);
    const includeLog = document.getElementById('bug-include-log').checked;
    const includePack = document.getElementById('bug-include-pack').checked;
    const includeContentLog = document.getElementById('bug-include-content-log')?.checked || false;
    const includeDriverLog = document.getElementById('bug-include-driver-log')?.checked || false;
    const includeHardware = document.getElementById('bug-include-hardware')?.checked || false;
    const statusEl = document.getElementById('bug-report-status');

    statusEl.innerHTML = `${t('tabSupport.bugReport.status.submitting')} <span class='status-spinner'>⏳</span>`;
    statusEl.className = "status-hint";
    btnSubmit.disabled = true;

    let logPath = null;
    let packPath = null;
    let contentLogZipPath = null;
    let tempZipToClean = null;

    try {

      // Prepare the Minecraft content log first: it can require user action
      // (enable logging -> restart MC), in which case we stop the submission.
      if (includeContentLog) {
        const zipPath = await prepareContentLogOrInstruct(statusEl, btnSubmit);
        if (zipPath === null) return;
        contentLogZipPath = zipPath;
      }

      if (includeLog) {
        logPath = "patcher.log";
        // English, like the copy buttons: the report is read by the developers.
        const logContent = englishLogText();
        await invoke("write_text_file", { path: logPath, content: logContent });
      }



      if (includePack) {
        const mode = document.querySelector('input[name="patch-mode"]:checked').value;
        if (mode === 'zip') {
          packPath = document.getElementById('zip-input-file').value;
        } else if (mode === 'marketplace') {
          statusEl.innerHTML = `${t('tabSupport.bugReport.status.zippingMarketplace')} <span class='status-spinner'>⏳</span>`;
          let expectedLogoHash = null;
          let expectedHasLangFile = null;
          let validStatsList = null;
          if (window.patchConfigs && window.patchConfigs.length > 0) {
            expectedLogoHash = window.patchConfigs[0].validation?.logo_hash || null;
            expectedHasLangFile = window.patchConfigs[0].validation?.has_lang_file || null;
          }
          const candidates = await invoke("scan_marketplace_packs", { expectedLogoHash, expectedHasLangFile, validStatsList });
          if (candidates && candidates.length > 0) {
            const tempRoot = defaultPaths.temp ? defaultPaths.temp.replace(/\\/g, "/") : ".";
            const zipOut = `${tempRoot}/bug_report_marketplace_pack.zip`;
            await invoke("pack_folder", { folderPath: candidates[0].path, outputZip: zipOut });
            packPath = zipOut;
            tempZipToClean = zipOut;
          }
        }
      }

      const description = document.getElementById('bug-description').value.trim();

      const res = await invoke("submit_bug_report", {
        discordName: discordName,
        description: description,
        logPath: logPath,
        packPath: packPath,
        contentLogZipPath: contentLogZipPath,
        includeDriverEvents: includeDriverLog,
        includeHardware: includeHardware,
        categories: categories
      });

      if (res && res.success) {
        let msg = t('tabSupport.bugReport.status.success', { caseId: res.caseId });
        if (res.replacedOld) {
            msg += `<br><br><span style="color: #fbbf24; font-size: 0.8rem;">${t('tabSupport.bugReport.status.replacedOldNote')}</span>`;
        }
        statusEl.innerHTML = msg;
        statusEl.className = "status-success";
      }

    } catch (err) {
      statusEl.innerText = t('tabSupport.bugReport.status.failed', { error: err });
      statusEl.className = "status-error";

      if (err.includes("User not found")) {
        showModal(t('tabSupport.bugReport.alerts.userNotFound', { error: err }), {
          title: t('tabSupport.bugReport.alerts.joinServerTitle'),
          confirm: true,
          okText: t('tabSupport.bugReport.alerts.joinDiscordBtn'),
          cancelText: t('common.cancel')
        }).then(async (joined) => {
          if (joined) {
            await invoke("open_url", { url: "https://discord.gg/YrMMmN2kc7" });
          }
        });
      }
    } finally {
      btnSubmit.disabled = false;
      if (logPath) {
        try { await invoke("delete_folders", { folders: [logPath] }); } catch (e) {}
      }
      if (tempZipToClean) {
        try { await invoke("delete_folders", { folders: [tempZipToClean] }); } catch (e) {}
      }
    }
  });
}

// One-click, fully anonymous report for a specific tracked issue (stretched/
// black/purple mob textures on NVIDIA cards). Unlike the general Bug
// Reporter above, no Discord name is asked for at all, and content log +
// hardware + GPU driver events are always included (not optional toggles),
// since diagnosing this specific bug needs all three every time. The
// category tag sent here ("NVIDIA Mob Texture Corruption") is what the
// server's retention job checks to exempt these reports from the usual
// 30/90-day auto-deletion until the case is marked resolved.
const KNOWN_ISSUE_CATEGORY = 'NVIDIA Mob Texture Corruption';

async function setupKnownIssueReporter() {
  const btnSubmit = document.getElementById('btn-submit-known-issue');
  if (!btnSubmit) return;

  btnSubmit.addEventListener('click', async () => {
    const statusEl = document.getElementById('known-issue-status');
    const description = document.getElementById('known-issue-description')?.value.trim() || '';

    statusEl.innerHTML = `${t('tabSupport.knownIssue.status.submitting')} <span class='status-spinner'>⏳</span>`;
    statusEl.className = "status-hint";
    btnSubmit.disabled = true;

    try {
      const contentLogZipPath = await prepareContentLogOrInstruct(statusEl, btnSubmit);
      if (contentLogZipPath === null) return;

      const res = await invoke("submit_bug_report", {
        discordName: null,
        description: description,
        logPath: null,
        packPath: null,
        contentLogZipPath: contentLogZipPath,
        includeDriverEvents: true,
        includeHardware: true,
        categories: [KNOWN_ISSUE_CATEGORY],
      });

      if (res && res.success) {
        statusEl.innerHTML = `${t('tabSupport.knownIssue.status.success', { caseId: res.caseId })}<br><br>` +
          `<span style="font-size: 0.8rem;">${t('tabSupport.knownIssue.status.retentionNotice')}</span>`;
        statusEl.className = "status-success";
      }
    } catch (err) {
      statusEl.innerText = t('tabSupport.knownIssue.status.failed', { error: err });
      statusEl.className = "status-error";
    } finally {
      btnSubmit.disabled = false;
    }
  });
}


// Check for Updates
async function checkForUpdates() {
  const badge = document.getElementById('update-badge');
  const btn = document.getElementById('btn-update-now');
  if (!badge) return;

  badge.className = "update-badge state-checking";
  delete badge.dataset.updateVersion;
  badge.setAttribute('data-i18n', 'sidebar.update.checking');
  badge.innerText = t('sidebar.update.checking');

  const allowBetaUpdates = localStorage.getItem('allow-beta-updates') === 'true';
  const isAdvanced = document.getElementById('chk-advanced-mode')?.checked;



  try {
    log(msg('log.update.checking'));
    const update = await invoke("plugin:updater|check");

    if (update) {
      const isBetaUpdate = update.version.endsWith('_b') || update.version.endsWith('-b') || update.version.endsWith('-0');
      const isAlphaUpdate = update.version.endsWith('_a') || update.version.endsWith('-a') || update.version.endsWith('-1');
      const userFacingVersion = update.version
        .replace('-b', '_b')
        .replace('-0', '_b')
        .replace('-a', '_a')
        .replace('-1', '_a');
      
      const isAdvanced = document.getElementById('chk-advanced-mode').checked;

      // If beta update but beta updates are disabled, ignore it
      if (isBetaUpdate && !allowBetaUpdates) {
        log(msg('log.update.betaSkipped', { version: userFacingVersion }));
        badge.className = "update-badge state-uptodate";
        delete badge.dataset.updateVersion;
      badge.setAttribute('data-i18n', 'sidebar.update.upToDate');
        badge.innerText = t('sidebar.update.upToDate');
        btn.classList.add('hidden-group');
        return;
      }

      // If alpha update but (beta updates are disabled OR advanced mode is disabled), ignore it
      if (isAlphaUpdate && (!allowBetaUpdates || !isAdvanced)) {
        log(msg('log.update.alphaSkipped', { version: userFacingVersion }));
        badge.className = "update-badge state-uptodate";
        delete badge.dataset.updateVersion;
      badge.setAttribute('data-i18n', 'sidebar.update.upToDate');
        badge.innerText = t('sidebar.update.upToDate');
        btn.classList.add('hidden-group');
        return;
      }

      log(msg('log.update.available', { version: userFacingVersion }));
      badge.className = "update-badge state-available";
      badge.removeAttribute('data-i18n');
      badge.dataset.updateVersion = userFacingVersion;
      badge.innerText = t('sidebar.update.available', { version: userFacingVersion });
      btn.classList.remove('hidden-group');
      
      btn.onclick = async () => {
        // Confirmation dialog to never force beta updates
        let updateType = "Stable";
        if (isBetaUpdate) updateType = "Beta";
        else if (isAlphaUpdate) updateType = "Alpha";
        
        let message = t('sidebar.update.confirmMessage', { type: updateType, version: userFacingVersion });

        if (isAlphaUpdate) {
          message += `\n\n${t('sidebar.update.alphaWarning')}`;
        }

        const confirmed = await showConfirm(
          message,
          t('sidebar.update.confirmTitle')
        );
        if (!confirmed) return;

        btn.disabled = true;
        btn.setAttribute('data-i18n', 'sidebar.update.updating');
        btn.innerText = t('sidebar.update.updating');
        log(msg('log.update.downloadingInstalling'));
        try {
          if (!update.rid) {
            throw msg('log.update.missingRid');
          }

          const onEvent = new Channel();
          onEvent.onmessage = (event) => {
            if (event.event === "Progress") {
              const current = event.data.chunkLength || 0;
              log(msg('log.update.downloadProgress', { bytes: current }));
            } else if (event.event === "Finished") {
              log(msg('log.update.downloadFinished'));
            }
          };

          await invoke("plugin:updater|download_and_install", { 
            rid: update.rid,
            onEvent: onEvent
          });
          
          log(msg('log.update.installed'), "success");
          await showAlert(t('sidebar.update.installed'));
        } catch (err) {
          log(msg('log.update.installFailed', { error: err }), 'error');
          await showAlert(t('sidebar.update.installFailed', { error: err }));
          btn.disabled = false;
          btn.setAttribute('data-i18n', 'sidebar.update.updateNow');
          btn.innerText = t('sidebar.update.updateNow');
        }
      };
    } else {
      log(msg('log.update.upToDate'));
      badge.className = "update-badge state-uptodate";
      delete badge.dataset.updateVersion;
      badge.setAttribute('data-i18n', 'sidebar.update.upToDate');
      badge.innerText = t('sidebar.update.upToDate');
      btn.classList.add('hidden-group');
    }
  } catch (err) {
    log(msg('log.update.checkFailed', { error: err }), 'warning');
    badge.className = "update-badge state-error";
    badge.setAttribute('data-i18n', 'sidebar.update.checkFailed');
    badge.innerText = t('sidebar.update.checkFailed');
    btn.classList.add('hidden-group');
  }
}

// App Settings State and Persistence
let appSettings = {
  defaultMode: 'marketplace',
  advancedMode: false,
  betaUpdates: false,
  cleanOld: true,
  autoCleanPatchCache: false,
  consoleHeight: 150,
  patchLibraryDir: '',
  publishAfterCreate: false,
  patchCreatorName: '',
  lastPatchPrTitle: '',
  lastPatchPrDescription: '',
  genInjectManifest: true,
  bugIncludeLog: true,
  bugIncludePack: false,
  bugIncludeContentLog: true,
  bugIncludeDriverLog: true,
  bugIncludeHardware: true,
  sidebarCollapsed: false,
  language: 'en'
};

async function loadSettings() {
  try {
    const raw = await invoke("load_settings");
    if (raw && raw !== "{}") {
      const parsed = JSON.parse(raw);
      appSettings = { ...appSettings, ...parsed };
    }
  } catch(e) {
    console.error("Failed to load settings", e);
  }
}

async function saveSettings() {
  try {
    await invoke("save_settings", { settings: JSON.stringify(appSettings, null, 2) });
  } catch(e) {
    console.error("Failed to save settings", e);
  }
}

// Initialize everything on page load
window.addEventListener('DOMContentLoaded', async () => {
  log(msg('log.app.initializing'));

  // Load user settings
  await loadSettings();

  // * Must run before any settings-dependent UI is wired up: the handlers below
  // * read labels out of an already-translated DOM.
  await initI18n(appSettings.language);
  // Lines logged before the locales loaded showed their bare key.
  repaintLogLines();

  const updateSetting = async (key, val) => {
    appSettings[key] = val;
    await saveSettings();
  };

  // Sidebar Toggle
  const sidebarToggleBtn = document.getElementById('btn-toggle-sidebar');
  const appHeader = document.querySelector('.app-header');
  const logoTypingText = document.getElementById('logo-typing-text');
  const logoAccentText = document.getElementById('logo-accent-text');
  
  const animateTyping = async (element, targetText) => {
    if (!element) return;
    let current = element.textContent;
    // Fast delete
    while (current.length > 0) {
      current = current.slice(0, -1);
      element.textContent = current;
      await new Promise(r => setTimeout(r, 15));
    }
    // Fast type
    for (let i = 1; i <= targetText.length; i++) {
      element.textContent = targetText.slice(0, i);
      await new Promise(r => setTimeout(r, 20));
    }
  };

  if (sidebarToggleBtn && appHeader) {
    if (appSettings.sidebarCollapsed) {
      appHeader.classList.add('collapsed');
      if (logoTypingText) logoTypingText.textContent = "A&S";
      if (logoAccentText) logoAccentText.textContent = "RTX";
    } else {
      if (logoTypingText) logoTypingText.textContent = "ACTIONS & STUFF";
      if (logoAccentText) logoAccentText.textContent = "RTX PATCHER";
    }
    
    sidebarToggleBtn.addEventListener('click', () => {
      const isCollapsed = appHeader.classList.toggle('collapsed');
      updateSetting('sidebarCollapsed', isCollapsed);
      animateTyping(logoTypingText, isCollapsed ? "A&S" : "ACTIONS & STUFF");
      animateTyping(logoAccentText, isCollapsed ? "RTX" : "RTX PATCHER");
    });
  }


  const syncToggle = (id1, id2, key, trigger = false) => {
    const el1 = document.getElementById(id1);
    const el2 = document.getElementById(id2);
    if (el1) {
      el1.checked = appSettings[key];
      el1.addEventListener('change', e => { 
        if (el2) el2.checked = e.target.checked; 
        updateSetting(key, e.target.checked); 
        if (trigger && el2) el2.dispatchEvent(new Event('change'));
      });
    }
    if (el2) {
      el2.checked = appSettings[key];
      el2.addEventListener('change', e => { 
        if (el1) el1.checked = e.target.checked; 
        updateSetting(key, e.target.checked); 
      });
    }
    if (trigger && el2) el2.dispatchEvent(new Event('change'));
  };

  // Select counterpart of syncToggle: mirrors two <select> elements onto one
  // setting, persists the change, and runs an optional side effect.
  const syncSelect = (id1, id2, key, onChange) => {
    const els = [document.getElementById(id1), document.getElementById(id2)].filter(Boolean);
    els.forEach(el => {
      el.value = appSettings[key];
      el.addEventListener('change', async e => {
        const val = e.target.value;
        els.forEach(other => { if (other !== e.target) other.value = val; });
        await updateSetting(key, val);
        if (onChange) await onChange(val);
      });
    });
  };

  // Language pickers. Both dropdowns are filled from the i18n registry rather
  // than from hardcoded <option> markup, so adding a language needs no change
  // here -- see src/i18n/registry.js.
  ['sel-language', 'set-language'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = '';
    for (const { code, label } of getLocales()) {
      const opt = document.createElement('option');
      opt.value = code;
      opt.textContent = label;
      el.appendChild(opt);
    }
    el.value = getLocale();
  });
  syncSelect('sel-language', 'set-language', 'language', code => setLocale(code));

  // Sidebar picker: closed it shows only the flag, opened it lists the names.
  // The hidden select stays the value holder, so syncSelect keeps working.
  const langSelect = document.getElementById('sel-language');
  const langButton = document.getElementById('btn-language');
  const langMenu = document.getElementById('language-menu');
  if (langSelect && langButton && langMenu) {
    const flagImg = (flag) => {
      const img = document.createElement('img');
      img.className = 'lang-picker-flag';
      img.src = flag;
      img.alt = '';
      return img;
    };
    const closeLangMenu = () => {
      langMenu.classList.add('hidden-group');
      langButton.setAttribute('aria-expanded', 'false');
    };
    const renderLangPicker = () => {
      const locales = getLocales();
      const current = locales.find(l => l.code === getLocale()) || locales[0];
      langButton.replaceChildren(flagImg(current.flag));
      langMenu.replaceChildren(...locales.map(({ code, label, flag }) => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'lang-picker-option';
        item.setAttribute('role', 'option');
        item.setAttribute('aria-selected', String(code === current.code));
        const name = document.createElement('span');
        name.textContent = label;
        item.append(flagImg(flag), name);
        item.addEventListener('click', () => {
          closeLangMenu();
          if (langSelect.value === code) return;
          langSelect.value = code;
          langSelect.dispatchEvent(new Event('change'));
        });
        return item;
      }));
    };
    langButton.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = langMenu.classList.toggle('hidden-group') === false;
      langButton.setAttribute('aria-expanded', String(open));
    });
    document.addEventListener('click', (e) => { if (!langMenu.contains(e.target)) closeLangMenu(); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeLangMenu(); });
    onLocaleChange(renderLangPicker);
    renderLangPicker();
  }

  // Sync settings tabs to main UI tabs
  syncToggle('set-advanced-mode', 'chk-advanced-mode', 'advancedMode', true);
  syncToggle('set-beta-updates', 'chk-beta-updates', 'betaUpdates', true);
  syncToggle('set-clean-patch-cache', null, 'autoCleanPatchCache');
  syncToggle('set-publish-after-create', 'gen-publish-library', 'publishAfterCreate');

  // Patch library folder picker, reusing the same select_directory command as
  // every other Browse button.
  const libDirInput = document.getElementById('set-patch-library-dir');
  if (libDirInput) libDirInput.value = appSettings.patchLibraryDir || '';
  const btnBrowseLib = document.getElementById('btn-browse-patch-library');
  if (btnBrowseLib) {
    btnBrowseLib.addEventListener('click', async () => {
      try {
        const dir = await invoke("select_directory", { title: "Select your local clone of the patch library repo" });
        if (!dir) return;
        if (libDirInput) libDirInput.value = dir;
        await updateSetting('patchLibraryDir', dir);
        log(msg('log.app.libraryFolderSet', { path: dir }));
      } catch (err) {
        log(msg('log.app.libraryFolderFailed', { error: err }), 'error');
      }
    });
  }

  // Publish the most recently created patch without rebuilding it.
  const btnPublishLast = document.getElementById('btn-publish-last-patch');
  if (btnPublishLast) {
    btnPublishLast.addEventListener('click', async () => {
      if (!lastCreatedPatchFolder) return;
      btnPublishLast.disabled = true;
      try {
        await withBusyLabel(btnPublishLast, `<i class="fas fa-spinner fa-spin"></i> ${t('tabUtils.genpatch.publishing')}`,
          () => publishPatchToLibrary(lastCreatedPatchFolder));
      } finally {
        btnPublishLast.disabled = false;
      }
    });
  }
  syncToggle('set-clean-old', 'chk-clean-old', 'cleanOld');
  syncToggle('set-gen-inject-manifest', 'gen-inject-manifest', 'genInjectManifest');
  syncToggle('set-bug-include-log', 'bug-include-log', 'bugIncludeLog');
  syncToggle('set-bug-include-pack', 'bug-include-pack', 'bugIncludePack');
  syncToggle('set-bug-include-content-log', 'bug-include-content-log', 'bugIncludeContentLog');
  syncToggle('set-bug-include-driver-log', 'bug-include-driver-log', 'bugIncludeDriverLog');
  syncToggle('set-bug-include-hardware', 'bug-include-hardware', 'bugIncludeHardware');

  // Telemetry consent + privacy controls (DSGVO)
  setupTelemetry();

  // Handle default mode
  const defaultModeSelect = document.getElementById('set-default-mode');
  if (defaultModeSelect) {
    defaultModeSelect.value = appSettings.defaultMode;
    defaultModeSelect.addEventListener('change', e => {
      updateSetting('defaultMode', e.target.value);
      const targetRadio = document.querySelector(`input[name="patch-mode"][value="${e.target.value}"]`);
      if (targetRadio && !targetRadio.disabled) {
        targetRadio.checked = true;
        targetRadio.dispatchEvent(new Event('change'));
      }
    });
  }
  
  // Actually apply the default mode to the UI initially
  const targetRadio = document.querySelector(`input[name="patch-mode"][value="${appSettings.defaultMode}"]`);
  if (targetRadio && !targetRadio.disabled) {
    targetRadio.checked = true;
    targetRadio.dispatchEvent(new Event('change'));
  }

  // API Tests
  document.getElementById('btn-test-github-api')?.addEventListener('click', async () => {
    const resEl = document.getElementById('api-test-results');
    if (!resEl) return;
    resEl.style.color = '#e2e8f0';
    resEl.textContent = t('tabAppSettings.diagnostics.testingGithub');
    try {
      const resp = await fetch('https://api.github.com/repos/Felix-Chaos/Actions-and-Stuff-RTX-Patcher/releases/latest');
      if (resp.ok) {
        const data = await resp.json();
        resEl.style.color = '#4ade80';
        resEl.textContent = t('tabAppSettings.diagnostics.githubOnline', { tag: data.tag_name });
      } else {
        resEl.style.color = '#ef4444';
        resEl.textContent = t('tabAppSettings.diagnostics.githubStatusError', { status: resp.status });
      }
    } catch(e) {
      resEl.style.color = '#ef4444';
      resEl.textContent = t('tabAppSettings.diagnostics.githubFetchFailed', { error: e.message });
    }
  });

  document.getElementById('btn-test-backend')?.addEventListener('click', async () => {
    const resEl = document.getElementById('api-test-results');
    if (!resEl) return;
    resEl.style.color = '#e2e8f0';
    resEl.textContent = t('tabAppSettings.diagnostics.pingingBackend');
    try {
      const resp = await invoke("greet", { name: "Test" });
      resEl.style.color = '#4ade80';
      resEl.textContent = t('tabAppSettings.diagnostics.backendResponding', { response: resp });
    } catch(e) {
      resEl.style.color = '#ef4444';
      resEl.textContent = t('tabAppSettings.diagnostics.backendError', { error: e });
    }
  });

  document.getElementById('btn-test-workspace')?.addEventListener('click', async () => {
    const resEl = document.getElementById('api-test-results');
    if (!resEl) return;
    resEl.style.color = '#e2e8f0';
    resEl.textContent = t('tabAppSettings.diagnostics.testingWorkspace');
    try {
      const paths = await invoke("get_default_paths");
      const foundPath = paths.premium_cache || paths.mc_resource_packs || paths.premiumCache || paths.mcResourcePacks;
      resEl.style.color = '#4ade80';
      resEl.textContent = t('tabAppSettings.diagnostics.workspaceFound', {
        path: foundPath || t('tabAppSettings.diagnostics.workspaceUnknown'),
      });
    } catch(e) {
      resEl.style.color = '#ef4444';
      resEl.textContent = t('tabAppSettings.diagnostics.workspaceError', { error: e });
    }
  });

  // Dynamically set version badge from backend/tauri.conf.json
  try {
    let appVersion = await invoke("get_app_version");
    appVersion = appVersion
      .replace("-b", "_b")
      .replace("-0", "_b")
      .replace("-a", "_a")
      .replace("-1", "_a");
    const versionBadge = document.getElementById('app-version-badge');
    if (versionBadge) {
      versionBadge.innerText = `v${appVersion}`;
    }
  } catch (err) {
    console.error("Failed to fetch app version:", err);
  }

  // Load latest patch versions
  try {
    const versions = await invoke("get_patch_versions");
    if (versions) {
      const packVerInput = document.getElementById('gen-pack-version');
      const patchVerInput = document.getElementById('gen-patch-version');
      if (packVerInput) packVerInput.value = versions.packVersion;
      if (patchVerInput) patchVerInput.value = versions.patchVersion;
    }
  } catch (err) {
    console.error("Failed to fetch patch versions:", err);
  }

  setupConsoleResize();
  wireVersionControls();
  await loadPatchConfigs();
  await refreshCachedPatches();
  setupCatalogueAutoRefresh();
  await bindPickers();
  setupUtilities();
  setupReleaseBuilder();
  setupBugReporter();
  setupKnownIssueReporter();
  await loadMotd();
  await loadOptionsProfiles();
  log(msg('log.app.ready'));
  
  // Hide release builder tab in non-dev builds
  try {
    const isDev = await invoke("is_dev_build");
    if (!isDev) {
      const releaseTab = document.querySelector('button[data-tab="release"]');
      if (releaseTab) {
        releaseTab.style.display = 'none';
      }
      // Create Patch is an author tool too
      const genpatchTab = document.querySelector('button[data-util="genpatch"]');
      if (genpatchTab) {
        genpatchTab.style.display = 'none';
      }
      document.querySelector('#utils-tool-select option[value="genpatch"]')?.remove();
    }
  } catch (e) {
    console.error("Failed to check dev build status:", e);
  }

  // The encryption module is optional, so its toggle starts hidden
  try {
    if (await invoke("patch_encryption_available")) {
      document.getElementById('gen-encrypt-target-row')?.classList.remove('hidden-group');
    }
  } catch (e) {
    console.error("Failed to check patch encryption support:", e);
  }

  // Copy target path button listener
  const btnCopyTgt = document.getElementById('btn-copy-tgt');
  if (btnCopyTgt) {
    btnCopyTgt.addEventListener('click', () => {
      const tgtInput = document.getElementById('custom-tgt');
      if (tgtInput && tgtInput.value) {
        navigator.clipboard.writeText(tgtInput.value).then(() => {
          // Success: show yellow check icon
          btnCopyTgt.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fbbf24" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-check"><path d="M20 6 9 17l-5-5"/></svg>`;
          setTimeout(() => {
            // Restore copy icon
            btnCopyTgt.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-copy"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`;
          }, 2000);
        }).catch((err) => {
          console.error("Failed to copy target path:", err);
        });
      }
    });
  }

  // Beta Updates Preference Toggle
  const betaChk = document.getElementById('chk-beta-updates');
  if (betaChk) {
    betaChk.checked = localStorage.getItem('allow-beta-updates') === 'true';
    betaChk.addEventListener('change', (e) => {
      localStorage.setItem('allow-beta-updates', e.target.checked ? 'true' : 'false');
      checkForUpdates();
    });
  }

  checkForUpdates();
});

