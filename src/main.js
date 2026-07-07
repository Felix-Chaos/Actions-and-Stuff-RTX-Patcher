// JavaScript Controller for Actions & Stuff RTX Patcher v3

// Destructure invoke and listen from Tauri Core
const { invoke, Channel } = window.__TAURI__ ? window.__TAURI__.core : { invoke: () => Promise.reject("Tauri not available"), Channel: class {} };
const { listen } = window.__TAURI__ ? window.__TAURI__.event : { listen: () => {} };

// Listen for backend log messages and route them to correct UI console
if (window.__TAURI__) {
  listen('app-log', (event) => {
    const { container, message, log_type } = event.payload;
    if (container === 'main') {
      log(message, log_type);
    } else {
      logTo(container, message, log_type);
    }
  });
}

function showModal(message, options = {}) {
  const {
    title = 'Notification',
    confirm = false,
    okText = 'OK',
    cancelText = 'Cancel'
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

function showAlert(message, title = 'Notification') {
  showModal(message, { title, confirm: false });
}

async function showConfirm(message, title = 'Confirm') {
  return showModal(message, { title, confirm: true });
}

// Override window.alert to use the in-app modal
window.alert = function(msg) {
  showAlert(msg);
};

// Global State
let patchConfigs = [];
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
function log(msg, type = 'info') {
  const line = document.createElement('div');
  line.className = `log-line ${type}`;
  line.innerText = `[${new Date().toLocaleTimeString()}] ${msg}`;
  consoleLogs.appendChild(line);
  consoleLogs.scrollTop = consoleLogs.scrollHeight;
}

function logTo(container, msg, type = 'info') {
  const el = document.getElementById(container);
  if (!el) return;
  const line = document.createElement('div');
  line.className = `log-line ${type}`;
  line.innerText = `[${new Date().toLocaleTimeString()}] ${msg}`;
  el.appendChild(line);
  el.scrollTop = el.scrollHeight;
}

function clearConsole() {
  consoleLogs.innerHTML = '<div class="log-line system">Console cleared. Waiting for process...</div>';
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
  for (let i = 0; i <= 4; i++) {
    updateStepState(i, 'idle');
  }
}

// Copy log helper
function copyLogsFromEl(elId, btnId) {
  const el = document.getElementById(elId);
  const btn = document.getElementById(btnId);
  if (!el) return;
  const text = Array.from(el.querySelectorAll('.log-line'))
    .map(l => l.innerText).join('\n');
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
    if (motdTitle) motdTitle.innerText = activeMotd.title;
    if (motdMessage) motdMessage.innerText = activeMotd.message || "";
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
            if (offlineTitle) offlineTitle.innerText = "Service Offline UI Preview (Dev Mode)";
            if (offlineMessage) offlineMessage.innerText = "This is just a preview of the offline box. The API is actually ONLINE right now.";
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
    if (motdContainer) motdContainer.classList.add('hidden-group'); // Hide from main page
    
    if (offlineContainer && offlineTitle) {
      try {
        const isDev = await invoke("is_dev_build");
        if (isDev) {
          offlineTitle.innerText = "Service Offline (Dev Mode)";
          if (offlineMessage) offlineMessage.innerText = "Could not connect to the Chaos dev backend. This box is only visible in Dev Mode.";
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

// Load configs and versions from Rust
async function loadPatchConfigs() {
  try {
    log("Loading patch configurations...");
    patchConfigs = await invoke("get_patch_configs");
    log(`Loaded ${patchConfigs.length} patch configuration profiles.`);
    
    // Extract unique packVersion strings and sort descending
    const uniqueAsVersions = Array.from(new Set(patchConfigs.map(c => c.packVersion)))
      .sort((a, b) => b.localeCompare(a, undefined, { numeric: true, sensitivity: 'base' }));

    const asSelect = document.getElementById('select-as-version');
    if (asSelect) {
      asSelect.innerHTML = '';
      uniqueAsVersions.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v;
        opt.innerText = `Version ${v}`;
        asSelect.appendChild(opt);
      });

      asSelect.addEventListener('change', (e) => {
        updatePatchVersionsList(e.target.value);
      });
    }

    if (uniqueAsVersions.length > 0) {
      updatePatchVersionsList(uniqueAsVersions[0]);
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
  } catch (err) {
    log(`Failed to load patch configs: ${err}`, 'error');
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

  patchSelect.innerHTML = '<option value="latest">Latest (Recommended)</option>';
  matching.forEach(c => {
    const ver = c.patchVersion || "1.0";
    const opt = document.createElement('option');
    opt.value = ver;
    opt.innerText = `Patch v${ver}`;
    patchSelect.appendChild(opt);
  });
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

      if (exactMatch) return exactMatch;

      // 2. Fallback to version string
      if (detectedCandidate.version && detectedCandidate.version !== 'Unknown') {
        const verMatch = sortedConfigs.find(c => c.packVersion === detectedCandidate.version);
        if (verMatch) return verMatch;
      }
    } else if (typeof detectedCandidate === 'string' && detectedCandidate !== 'Unknown') {
      const verMatch = sortedConfigs.find(c => c.packVersion === detectedCandidate);
      if (verMatch) return verMatch;
    }
    // Default to the highest pack version config
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
    log(`Could not open explorer: ${err}`, 'warning');
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
  } catch (_) {
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
          log(`Selected: ${result}`);
        }
      } catch (err) {
        log(`Picker error: ${err}`, 'error');
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
      alert("Please select both source folder and destination path.");
      return;
    }
    
    try {
      log(`Starting deterministic pack of: ${src}`);
      await invoke("pack_folder", { folderPath: src, outputZip: dst });
      log(`Successfully created deterministic pack at ${dst}`, 'success');
      alert(`Pack created successfully at:\n${dst}`);
    } catch (err) {
      log(`Packing failed: ${err}`, 'error');
      alert(`Packing failed:\n${err}`);
    }
  });

  document.getElementById('btn-run-extract').addEventListener('click', async () => {
    const src = document.getElementById('extract-src-file').value;
    const dst = document.getElementById('extract-dst-folder').value;
    
    if (!src || !dst) {
      alert("Please select both source archive and destination folder.");
      return;
    }
    
    try {
      log(`Extracting: ${src} to ${dst}`);
      await invoke("extract_archive", { zipPath: src, outputDir: dst });
      log(`Successfully extracted files to ${dst}`, 'success');
      alert(`Extraction complete!`);
    } catch (err) {
      log(`Extraction failed: ${err}`, 'error');
      alert(`Extraction failed:\n${err}`);
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

    if (!patchedDir || !decryptedDir || !encryptedDir || !outputDir) {
      alert("Please fill in all four folder paths before creating patches.");
      return;
    }

    const gLog = document.getElementById('genpatch-logs');
    const gLog_fn = (msg, type = 'info') => logTo('genpatch-logs', msg, type);

    gLog.innerHTML = '<div class="log-line system">Starting patch creation...</div>';
    document.getElementById('btn-run-gen-patch').disabled = true;

    try {
      gLog_fn(`Pack Version: ${packVer}  |  Patch Version: ${patchVer}`);

      if (injectManifest) {
          gLog_fn(`  Injecting baseline custom manifest into source directories...`);
          try {
              await invoke("inject_custom_manifest_to_target", { targetDir: decryptedDir, packVer: "", patchVer: "" });
          } catch (e) {
              gLog_fn(`  ⚠️ Could not inject baseline manifest: ${e}`, "warning");
          }

          gLog_fn(`  Injecting versioned custom manifest into patched target...`);
          try {
              await invoke("inject_custom_manifest_to_target", { targetDir: patchedDir, packVer: packVer, patchVer: patchVer });
          } catch (e) {
              gLog_fn(`  ⚠️ Could not inject versioned manifest: ${e}`, "warning");
          }
      }

      // Step 1: Compress the Encrypted (Marketplace) source → encrypted.vcdiff source
      gLog_fn(`[1/4] Compressing encrypted source: ${encryptedDir}`);
      const encZip = outputDir + "/_temp_source_enc.zip";
      await invoke("pack_folder", { folderPath: encryptedDir, outputZip: encZip });
      gLog_fn(`  ✓ Encrypted source ZIP ready`);

      // Step 2: Compress the Decrypted (vanilla) source → decrypted.vcdiff source
      gLog_fn(`[2/4] Compressing decrypted source: ${decryptedDir}`);
      const decZip = outputDir + "/_temp_source_dec.zip";
      await invoke("pack_folder", { folderPath: decryptedDir, outputZip: decZip });
      gLog_fn(`  ✓ Decrypted source ZIP ready`);

      // Step 3: Compress patched (target) folder → target ZIP
      gLog_fn(`[3/4] Preparing patched target: ${patchedDir}`);
      const tgtZip = outputDir + "/_temp_target.zip";
      const tempTargetDir = outputDir + "/_temp_target_dir";
      
      const extractBrarchives = document.getElementById('gen-extract-brarchives').checked;
      const replaceUnchanged = document.getElementById('gen-replace-unchanged').checked;
      if (extractBrarchives) {
        gLog_fn(`  Extracting Brarchives in source and target...`);
        await invoke("extract_brarchives_in_workspace", { workspace: decryptedDir });
        await invoke("extract_brarchives_in_workspace", { workspace: patchedDir });
        await invoke("extract_brarchives_in_workspace", { workspace: encryptedDir });
      }

      // Run new replace logic
      await invoke("prepare_patch_target", {
        decryptedDir: decryptedDir,
        rtxDir: patchedDir,
        encryptedDir: encryptedDir,
        tempTargetDir: tempTargetDir,
        replaceUnchanged: replaceUnchanged
      });

      await invoke("pack_folder", { folderPath: tempTargetDir, outputZip: tgtZip });
      gLog_fn(`  ✓ Patched target ZIP ready`);

      // Step 4: Generate both patches
      gLog_fn(`[4/4] Generating VCDIFF patches...`);

      const folderName = `Actions & Stuff for RTX ${packVer} V${patchVer}`;
      const finalOutputDir = outputDir + "/" + folderName;

      const encPatch = finalOutputDir + "/encrypted.vcdiff";
      const decPatch = finalOutputDir + "/decrypted.vcdiff";

      gLog_fn(`  Encoding encrypted.vcdiff (source: encrypted, target: patched)...`);
      await invoke("generate_xdelta_patch", { sourceFile: encZip, targetFile: tgtZip, patchFile: encPatch });
      gLog_fn(`  ✓ encrypted.vcdiff created`);

      gLog_fn(`  Encoding decrypted.vcdiff (source: decrypted, target: patched)...`);
      await invoke("generate_xdelta_patch", { sourceFile: decZip, targetFile: tgtZip, patchFile: decPatch });
      gLog_fn(`  ✓ decrypted.vcdiff created`);
      
      // Calculate patch stats from the encrypted directory
      gLog_fn(`  Calculating patch stats from ${encryptedDir}...`);
      let patchStats = null;
      try {
          patchStats = await invoke("calculate_patch_stats", { folderPath: encryptedDir });
          gLog_fn(`  ✓ Stats calculated: ${patchStats.files} files, ${patchStats.dirs} dirs`);
      } catch (err) {
          gLog_fn(`  ⚠️ Failed to calculate stats: ${err}`, "warning");
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
      gLog_fn(`  ✓ patch_config.json created`);

      // Clean temp zips and folders
      await invoke("delete_folders", { folders: [encZip, decZip, tgtZip, tempTargetDir] });

      gLog_fn(`✅ All patches created successfully in: ${finalOutputDir}`, 'success');
      gLog_fn(`   Pack: ${packVer}  |  Patch: ${patchVer}`, 'success');

      // Save current patch version persistently
      try {
        await invoke("save_patch_versions", { packVersion: packVer, patchVersion: patchVer });
      } catch (err) {
        console.error("Failed to save patch version:", err);
      }

      // Open output folder in Explorer
      try { await invoke("open_in_explorer", { path: finalOutputDir }); } catch (_) {}

    } catch (err) {
      gLog_fn(`❌ Patch creation failed: ${err}`, 'error');
      alert(`Patch creation failed:\n${err}`);
    } finally {
      document.getElementById('btn-run-gen-patch').disabled = false;
    }
  });

  // Copy / Clear genpatch log
  const btnCopyGenpatch = document.getElementById('btn-copy-genpatch-log');
  if (btnCopyGenpatch) btnCopyGenpatch.addEventListener('click', () => copyLogsFromEl('genpatch-logs', 'btn-copy-genpatch-log'));
  const btnClearGenpatch = document.getElementById('btn-clear-genpatch-log');
  if (btnClearGenpatch) btnClearGenpatch.addEventListener('click', () => {
    document.getElementById('genpatch-logs').innerHTML = '<div class="log-line system">Ready to create patches...</div>';
  });

  document.getElementById('btn-run-util-br').addEventListener('click', async () => {
    const folder = document.getElementById('util-br-folder').value;
    if (!folder) {
      alert("Please select a target folder.");
      return;
    }
    
    try {
      log(`Running standalone Brarchive extraction on: ${folder}`);
      const found = await invoke("extract_brarchives_in_workspace", { workspace: folder });
      if (found) {
        log(`Successfully extracted brarchives inside ${folder}`, 'success');
        alert("Brarchive extraction completed successfully!");
      } else {
        log(`No brarchives found to extract in: ${folder}`, 'warning');
        alert("Completed: No __brarchive folders found to extract.");
      }
    } catch (err) {
      log(`Brarchive extraction failed: ${err}`, 'error');
      alert(`Extraction failed:\n${err}`);
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
    const select = document.getElementById('options-file-select');
    select.innerHTML = '<option value="">-- Choose a Profile --</option>';
    
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
        document.getElementById('rtx-settings-grid').innerHTML = '<div class="placeholder-text">Select an options.txt profile to read settings...</div>';
        document.getElementById('btn-save-settings').disabled = true;
        document.getElementById('btn-best-settings').disabled = true;
      }
    });
  } catch (err) {
    log(`Failed to list options.txt profiles: ${err}`, 'error');
  }
}

async function loadOptionsData(path) {
  try {
    log(`Reading options file: ${path}`);
    const data = await invoke("read_options", { path });
    
    const rtxKeys = {
      'gfx_raytracing': { label: 'Ray Tracing', type: 'bool' },
      'gfx_upscaling': { label: 'Upscaling / DLSS', type: 'bool' },
      'raytracing_viewdistance': { label: 'Ray Tracing View Distance (Chunks)', type: 'number' },
      'gfx_max_framerate': { label: 'Max Framerate', type: 'number' },
      'gfx_vsync': { label: 'VSync', type: 'bool' },
      'enable_dithering_blocks': { label: 'Block Dithering', type: 'bool' },
      'enable_dithering_mobs': { label: 'Mob Dithering', type: 'bool' }
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
      labelSpan.innerText = cfg.label;
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
    log(`Failed to read options: ${err}`, 'error');
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
    log(`Saving configuration edits...`);
    await invoke("write_options", { path: selectedOptionsPath, changes });
    log(`Successfully updated options.txt config!`, 'success');
    alert("Settings applied successfully!");
  } catch (err) {
    log(`Failed to write settings: ${err}`, 'error');
    alert(`Failed to save settings:\n${err}`);
  }
});

document.getElementById('btn-best-settings').addEventListener('click', () => {
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
  
  log("Automatically loaded best RTX settings into the editor. Click 'Apply Settings' to write them to options.txt.", "info");
  alert("Best settings set in the editor! Click 'Apply Settings' to save them.");
});


// Cleaner panel setup
let cleanablePacksPaths = [];

document.getElementById('btn-scan-cleaner').addEventListener('click', async () => {
  try {
    log("Scanning Minecraft folders for old RTX packs...");
    cleanablePacksPaths = await invoke("get_cleanable_packs");
    
    const countTag = document.getElementById('clean-results-count');
    countTag.innerText = `${cleanablePacksPaths.length} found`;
    
    const list = document.getElementById('clean-results-list');
    list.innerHTML = '';
    
    if (cleanablePacksPaths.length === 0) {
      list.innerHTML = '<div class="placeholder-text">No old Actions & Stuff packs found. Your folders are clean!</div>';
      document.getElementById('btn-run-cleaner').disabled = true;
      log("Scan finished. Clean state verified.");
    } else {
      cleanablePacksPaths.forEach(p => {
        const item = document.createElement('div');
        item.className = 'clean-item';
        
        const pathSpan = document.createElement('span');
        pathSpan.className = 'clean-item-path';
        pathSpan.innerText = p;
        item.appendChild(pathSpan);
        
        const labelSpan = document.createElement('span');
        const parts = p.split(/[\\\/]/);
        labelSpan.innerText = parts[parts.length - 1] || p;
        item.appendChild(labelSpan);
        
        list.appendChild(item);
      });
      document.getElementById('btn-run-cleaner').disabled = false;
      log(`Scan finished. Found ${cleanablePacksPaths.length} cleanable paths.`);
    }
  } catch (err) {
    log(`Scan failed: ${err}`, 'error');
  }
});

document.getElementById('btn-run-cleaner').addEventListener('click', async () => {
  if (cleanablePacksPaths.length === 0) return;
  const confirmDelete = await showConfirm(
    `Are you sure you want to delete all ${cleanablePacksPaths.length} located folders?`,
    'Confirm Deletion'
  );
  if (!confirmDelete) return;
  
  try {
    log("Deleting located folders...");
    const deletedCount = await invoke("delete_folders", { folders: cleanablePacksPaths });
    log(`Cleaner: Successfully deleted ${deletedCount} folders.`, 'success');
    alert(`Clean up complete! Deleted ${deletedCount} folder(s).`);
    
    document.getElementById('clean-results-list').innerHTML = '<div class="placeholder-text">Click Scan Folders to begin search...</div>';
    document.getElementById('clean-results-count').innerText = '0 found';
    document.getElementById('btn-run-cleaner').disabled = true;
  } catch (err) {
    log(`Deletion error: ${err}`, 'error');
    alert(`Clean up failed:\n${err}`);
  }
});

// CORE PATCHER PIPELINE
let finalPatchedPath = "";

document.getElementById('btn-start-patch').addEventListener('click', async () => {
  const mode = document.querySelector('input[name="patch-mode"]:checked').value;
  const selectionMode = document.getElementById('version-selection-mode').value;
  const cleanOld = document.getElementById('chk-clean-old').checked;
  const isAdvanced = document.getElementById('chk-advanced-mode').checked;
  const extractBrarchives = isAdvanced && document.getElementById('chk-extract-brarchives').checked;
  
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
  
  log(`Starting patch pipeline in [${mode}] mode.`);
  log(`Configuration selection mode: ${selectionMode}`);
  log(`Automatic remnant cleanup option: ${cleanOld ? "Enabled" : "Disabled"}`);
  log(`Brarchive extraction option: ${extractBrarchives ? "Enabled" : "Disabled"}`);
  
  try {
    let sourceZipPath = "";
    let patchConfigToUse = null;
    
    // ----------------------------------------
    // STEP 0: SCAN & VERIFY
    // ----------------------------------------
    updateStepState(0, 'active');
    updateStatus("Verifying Content", "Analyzing patch requirements...", '🔍');
    updateProgress(10);
    
    if (mode === 'marketplace') {
      log("Scanning premium cache locations for purchased Marketplace pack candidate...");
      let expectedStats = { expectedLogoHash: null, expectedHasLangFile: null, validStatsList: null };
      if (selectionMode === 'manual') {
        const asVer = document.getElementById('select-as-version').value;
        const ptVer = document.getElementById('select-patch-version').value;
        const selected = patchConfigs.find(c => c.packVersion === asVer && c.patchVersion === ptVer);
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
      const candidates = await invoke("scan_marketplace_packs", expectedStats);
      log(`Found ${candidates.length} candidate packs in premium cache.`);
      
      candidates.forEach((cand, idx) => {
        log(`Candidate [${idx + 1}]:`);
        log(`  Folder Name: ${cand.folder_name}`);
        log(`  Full Path:   ${cand.path}`);
        log(`  Version:     ${cand.version}`);
        log(`  Contents:    ${cand.files_count} files, ${cand.dirs_count} directories`);
        log(`  Match Score: ${cand.score}`);
      });
      
      if (candidates.length === 0) {
        log("No valid Marketplace pack found. Requesting manual folder selection...");
        const browsePath = await invoke("select_directory", { title: "Browse and select your Actions & Stuff pack folder manually" });
        if (!browsePath) {
          throw "User cancelled manual browse. Patch aborted.";
        }
        log(`Using manually browsed pack directory: ${browsePath}`);
        patchConfigToUse = resolvePatchConfig(selectionMode, null);
      } else {
        const best = candidates[0];
        log(`Auto-selected candidate pack:`);
        log(`  Path: "${best.path}"`);
        log(`  Version: ${best.version}`);
        log(`  Complexity: ${best.files_count} files and ${best.dirs_count} folders`);
        
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
              throw `Validation failed: Pack seems corrupted or modified! Expected ~${stats.files} files and ${stats.dirs} folders, but found ${best.files_count} files and ${best.dirs_count} folders.`;
          }
        }

        // If selection is manual, we check if the selected patch pack version matches the detected pack version
        // To be safe, if we resolved an exact patchConfigToUse, its packVersion is the best determination of truth
        let determinedVersion = best.version;
        if (patchConfigToUse && patchConfigToUse.packVersion) {
            determinedVersion = patchConfigToUse.packVersion;
        }

        if (selectionMode === 'manual' && patchConfigToUse.packVersion !== determinedVersion) {
          log(`Warning: Target patch version (${patchConfigToUse.packVersion}) does not match detected pack version (${determinedVersion}).`, 'warning');
          const proceed = await showConfirm(
            `Warning: The selected patch version (${patchConfigToUse.packVersion}) differs from your installed pack version (${determinedVersion}).\n\nDo you want to proceed anyway?`,
            'Version Mismatch'
          );
          if (!proceed) {
            throw "User aborted due to version mismatch.";
          }
        }
      }
      
      updateStepState(0, 'completed');
      
      // STEP 1: COMPRESSION / NORMALIZATION
      updateStepState(1, 'active');
      
      const sourcePackPath = candidates.length > 0 ? candidates[0].path : document.getElementById('custom-src').value;
      const tempRoot = defaultPaths.temp ? defaultPaths.temp.replace(/\\/g, "/") : ".";
      const baseName = sourcePackPath.split(/[\\/]/).pop() || "source";
      const zipOut = `${tempRoot}/${baseName}_vanilla.zip`;
      let targetFolder = sourcePackPath;
 
      if (extractBrarchives) {
        updateStatus("Extracting Brarchives (Beta)", "Copying and extracting brarchives...", '📦');
        updateProgress(15);
        targetFolder = `${tempRoot}/${baseName}_mp_extracted`;
        log("Staging Marketplace files to extract Brarchives...");
        log(`  Staging Source: "${sourcePackPath}"`);
        log(`  Staging Target: "${targetFolder}"`);
        await invoke("stage_and_extract_brarchives", { sourceDir: sourcePackPath, tempDir: targetFolder });
        log("Staging and brarchive extraction complete.");
      }
 
      updateStatus("Compressing Pack", "Generating deterministic ZIP of source pack...", '📦');
      updateProgress(25);
      
      log(`Starting deterministic ZIP compression...`);
      log(`  Compressing:  "${targetFolder}"`);
      log(`  Output ZIP:   "${zipOut}"`);
      await invoke("pack_folder", { folderPath: targetFolder, outputZip: zipOut });
      log(`Successfully created deterministic source ZIP: "${zipOut}"`);
 
      if (extractBrarchives) {
        log(`Cleaning up temporary staged folder: "${targetFolder}"`);
        await invoke("delete_folders", { folders: [targetFolder] });
        log(`Staged folder deleted.`);
      }
 
      sourceZipPath = zipOut;
      updateStepState(1, 'completed');
      
    } else if (mode === 'zip') {
      // Use pre-selected file from the Zip mode file picker
      let selectedZip = document.getElementById('zip-input-file') ? document.getElementById('zip-input-file').value : '';
      if (!selectedZip) {
        log("No file pre-selected — prompting picker...");
        selectedZip = await invoke("select_file", {
          title: "Select Minecraft Resource Pack to Patch",
          filter: "Minecraft Packs (*.zip *.mcpack)|*.zip;*.mcpack"
        });
      }
      if (!selectedZip) {
        throw "No file selected. Patch aborted.";
      }
      log(`Selected pack archive: "${selectedZip}"`);
      updateStepState(0, 'completed');
      
      updateStepState(1, 'active');
      updateStatus("Extracting & Normalizing", "Unpacking ZIP and removing licensing signatures...", '⚙️');
      updateProgress(20);
      
      const tempRoot = defaultPaths.temp ? defaultPaths.temp.replace(/\\/g, "/") : ".";
      const baseName = selectedZip.split(/[\\/]/).pop() || "pack";
      
      const tempExtract = `${tempRoot}/${baseName}_extracted`;
      log(`Extracting ZIP file to temp directory:`);
      log(`  Source ZIP: "${selectedZip}"`);
      log(`  Target Dir: "${tempExtract}"`);
      await invoke("extract_archive", { zipPath: selectedZip, outputDir: tempExtract });
      log("ZIP extraction completed successfully.");
      
      log("Normalizing contents: deleting license signatures (contents.json, signatures.json, splashes.json, sounds.json) and injecting custom manifest...");
      log(`  Target Dir: "${tempExtract}"`);
      await invoke("normalize_extracted_pack", { extractDir: tempExtract });
      log("Normalization and custom manifest injection finished.");
 
      if (extractBrarchives) {
        updateStatus("Extracting Brarchives (Beta)", "Extracting brarchives inside pack context...", '⚙️');
        updateProgress(25);
        log(`Recursively scanning for and extracting .brarchive files in: "${tempExtract}"`);
        await invoke("extract_brarchives_in_workspace", { workspace: tempExtract });
        log("Nested brarchive extraction complete.");
      }
      
      const normalizedZip = `${tempRoot}/${baseName}_normalized.zip`;
      updateStatus("Compressing Normalized", "Generating deterministic ZIP of normalized pack...", '⚙️');
      updateProgress(35);
      log(`Re-compressing normalized files into deterministic ZIP:`);
      log(`  Compressing:  "${tempExtract}"`);
      log(`  Output ZIP:   "${normalizedZip}"`);
      await invoke("pack_folder", { folderPath: tempExtract, outputZip: normalizedZip });
      log("Re-compression complete.");
      
      log(`Deleting temporary extraction directory: "${tempExtract}"`);
      await invoke("delete_folders", { folders: [tempExtract] });
      log("Temporary directory cleaned.");
      
      sourceZipPath = normalizedZip;
      patchConfigToUse = resolvePatchConfig(selectionMode, null);
      
      updateStepState(1, 'completed');
      
    } else if (mode === 'custom') {
      const src = document.getElementById('custom-src').value;
      const tgt = document.getElementById('custom-tgt').value;
      const patch = document.getElementById('custom-patch').value;
      
      if (!src || !tgt || !patch) {
        throw "Custom mode requires specifying source, target, and patch paths.";
      }
      
      log(`Custom Patch parameters:`);
      log(`  Source: "${src}"`);
      log(`  Target: "${tgt}"`);
      log(`  Patch:  "${patch}"`);
      
      updateStepState(0, 'completed');
      updateStepState(1, 'active');
      
      if (src.endsWith('.zip') || src.endsWith('.mcpack')) {
        const tempRoot = defaultPaths.temp ? defaultPaths.temp.replace(/\\/g, "/") : ".";
        const baseName = src.split(/[\\/]/).pop() || "custom";
        if (extractBrarchives) {
          updateStatus("Extracting Brarchives (Beta)", "Extracting brarchives inside custom source ZIP...", '📦');
          updateProgress(15);
          const tempExtract = `${tempRoot}/${baseName}_custom_extracted`;
          log(`Extracting custom source ZIP: "${src}" to "${tempExtract}"`);
          await invoke("extract_archive", { zipPath: src, outputDir: tempExtract });
          log(`Extracting brarchives recursively inside: "${tempExtract}"`);
          await invoke("extract_brarchives_in_workspace", { workspace: tempExtract });
          const customZip = `${tempRoot}/${baseName}_custom_source.zip`;
          updateStatus("Compressing Custom", "Generating deterministic ZIP...", '📦');
          updateProgress(30);
          log(`Creating deterministic zip: "${customZip}" from "${tempExtract}"`);
          await invoke("pack_folder", { folderPath: tempExtract, outputZip: customZip });
          log(`Cleaning temporary folder: "${tempExtract}"`);
          await invoke("delete_folders", { folders: [tempExtract] });
          sourceZipPath = customZip;
        } else {
          updateStatus("Copying Source", "Using source ZIP...", '📦');
          updateProgress(30);
          log(`Source is already ZIP. Using directly: "${src}"`);
          sourceZipPath = src;
        }
      } else {
        const tempRoot = defaultPaths.temp ? defaultPaths.temp.replace(/\\/g, "/") : ".";
        const baseName = src.split(/[\\/]/).pop() || "custom";
        if (extractBrarchives) {
          updateStatus("Extracting Brarchives (Beta)", "Copying and extracting custom brarchives...", '📦');
          updateProgress(15);
          const targetFolder = `${tempRoot}/${baseName}_custom_staged`;
          log(`Staging custom source folder to Extract Brarchives:`);
          log(`  Staging Source: "${src}"`);
          log(`  Staging Target: "${targetFolder}"`);
          await invoke("stage_and_extract_brarchives", { sourceDir: src, tempDir: targetFolder });
          const customZip = `${tempRoot}/${baseName}_custom_source.zip`;
          updateStatus("Compressing Custom", "Generating deterministic ZIP...", '📦');
          updateProgress(30);
          log(`Creating deterministic ZIP: "${customZip}" from "${targetFolder}"`);
          await invoke("pack_folder", { folderPath: targetFolder, outputZip: customZip });
          log(`Cleaning temporary folder: "${targetFolder}"`);
          await invoke("delete_folders", { folders: [targetFolder] });
          sourceZipPath = customZip;
        } else {
          updateStatus("Compressing Custom", "Compressing custom directory...", '📦');
          updateProgress(30);
          const customZip = `${tempRoot}/${baseName}_custom_source.zip`;
          log(`Source is folder. Creating deterministic zip: "${customZip}" from "${src}"`);
          await invoke("pack_folder", { folderPath: src, outputZip: customZip });
          sourceZipPath = customZip;
        }
      }
      
      updateStepState(1, 'completed');
    }
    
    // STEP 2: CLEAN REMNANTS
    updateStepState(2, 'active');
    if (cleanOld) {
      updateStatus("Cleaning Remnants", "Scanning and deleting old patched resource pack directories...", '🧹');
      updateProgress(45);
      log("Scanning com.mojang directories for old actions & stuff remnant folders to clean...");
      const cleanable = await invoke("get_cleanable_packs");
      if (cleanable.length > 0) {
        log(`Found ${cleanable.length} remnant folders:`);
        cleanable.forEach(p => log(`  Remnant: "${p}"`));
        log(`Deleting remnant folders...`);
        const cleaned = await invoke("delete_folders", { folders: cleanable });
        log(`Successfully removed ${cleaned} old pack directories.`);
      } else {
        log("No old remnant directories found.");
      }
    } else {
      log("Remnant cleaning skipped by user preference.");
    }
    updateStepState(2, 'completed');
    
    // STEP 3: APPLY RTX PATCH
    updateStepState(3, 'active');
    updateStatus("Applying RTX Patch", "Running high-performance XDelta decoder...", '⚡');
    updateProgress(65);
    
    let patchFilePath = "";
    let finalOutputPath = "";
    
    if (mode === 'custom') {
      patchFilePath = document.getElementById('custom-patch').value;
      finalOutputPath = document.getElementById('custom-tgt').value;
    } else {
      if (!patchConfigToUse) {
        throw "No valid patch configuration found to match targets.";
      }
      
      const isEncrypted = mode === 'marketplace';
      const patchKey = isEncrypted ? 'encrypted' : 'decrypted';
      
      let relPatch = patchConfigToUse.patches && patchConfigToUse.patches[patchKey]
        ? patchConfigToUse.patches[patchKey]
        : `assets/Patches/${patchConfigToUse.folder_name}/${isEncrypted ? 'encrypted.vcdiff' : 'decrypted.vcdiff'}`;
        
      patchFilePath = relPatch;
      
      const sourcePackPath = sourceZipPath;
      const idx = sourcePackPath.lastIndexOf('.');
      finalOutputPath = idx !== -1 
        ? `${sourcePackPath.substring(0, idx)}_RTX_Patched.zip`
        : `${sourcePackPath}_RTX_Patched.zip`;
    }
    
    log(`APPLYING PATCH FILE:`);
    log(`  Patch:  "${patchFilePath}"`);
    log(`  Source: "${sourceZipPath}"`);
    log(`  Output: "${finalOutputPath}"`);
    log("Running XDelta patch execution...");
    
    await invoke("run_xdelta_patch", {
      sourceZip: sourceZipPath,
      patchFile: patchFilePath,
      outputFile: finalOutputPath
    });
    
    log("Patch application completed successfully!", 'success');
    updateStepState(3, 'completed');
    
    // Clean intermediate zip
    if (mode === 'marketplace' || mode === 'zip' || (mode === 'custom' && !document.getElementById('custom-src').value.endsWith('.zip'))) {
      log(`Cleaning temporary source ZIP: "${sourceZipPath}"`);
      await invoke("delete_folders", { folders: [sourceZipPath] });
      log("Temporary source ZIP cleaned.");
    }
    
    // STEP 4: IMPORT PACK
    updateStepState(4, 'active');
    updateStatus("Patch Done", "Ready to import into Minecraft!", '🎉');
    updateProgress(100);
    
    finalPatchedPath = finalOutputPath;
    document.getElementById('progress-actions-container').classList.remove('hidden-group');
    document.getElementById('btn-install-pack').classList.remove('hidden-group');
    document.getElementById('btn-copy-log-large').classList.remove('hidden-group');
    log("SUCCESS: Patcher completed all steps. Click 'Install Pack' to import and play!", 'success');
    
  } catch (err) {
    log(`PIPELINE FAILURE: ${err}`, 'error');
    updateStatus("Patch Failed", "An error occurred during execution.", '❌');
    updateProgress(0);
    document.getElementById('progress-actions-container').classList.remove('hidden-group');
    document.getElementById('btn-install-pack').classList.add('hidden-group');
    document.getElementById('btn-copy-log-large').classList.remove('hidden-group');
    document.getElementById('btn-report-bug-quick').classList.remove('hidden-group');
  } finally {
    document.getElementById('btn-start-patch').disabled = false;
  }
});

document.getElementById('btn-install-pack').addEventListener('click', async () => {
  if (!finalPatchedPath) return;
  const btn = document.getElementById('btn-install-pack');
  const originalText = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Installing...`;

  try {
    log(`Launching installer for: ${finalPatchedPath}`);
    const actualMcpack = await invoke("install_mcpack", { outputFile: finalPatchedPath });
    log(`Successfully installed pack to: ${actualMcpack}`, 'success');
    updateStepState(4, 'completed');
    btn.classList.add('hidden-group');
  } catch (err) {
    log(`Install failed: ${err}`, 'error');
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
  updateStatus("Ready to Patch", "Configure options and click Apply", '💤');
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
  const bLog = (msg, type = 'info') => logTo('build-logs', msg, type);

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
    if (relHint) relHint.innerText = `Current: ${versionBadge.innerText}`;
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
      if (!newVer) { alert("Please enter a version number."); return; }
      try {
        await invoke("update_app_version", { version: newVer });
        if (relHint) relHint.innerText = `Current: v${newVer} (saved)`;
        if (versionBadge) versionBadge.innerText = `v${newVer}`;
      } catch (err) {
        bLog(`Failed to update app version: ${err}`, 'error');
        alert(`Failed to update app version:\n${err}`);
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
            `A release build for version v${currentVersion} already exists in the output folder.\n\nDo you want to overwrite it?`,
            { title: 'Build Already Exists', confirm: true, okText: 'Overwrite', cancelText: 'Cancel' }
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
    buildLog.innerHTML = `<div class="log-line system">Starting build (${buildType})...</div>`;
    
    if (btnBuildAll) btnBuildAll.disabled = true;
    if (btnBuildInstallers) btnBuildInstallers.disabled = true;
    if (btnBuildPortable) btnBuildPortable.disabled = true;

    try {
      await invoke("run_release_build", { buildType: buildType });
    } catch (err) {
      buildLog.innerHTML += `<div class="log-line error">Failed to run build: ${err}</div>`;
      alert(`Failed to run release build:\n${err}`);
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
        log(`Failed to open bundle folder: ${err}`, 'error');
        alert(`Failed to open bundle folder:\n${err}`);
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
        log(`Failed to open patches folder: ${err}`, 'error');
        alert(`Failed to open patches folder:\n${err}`);
      }
    });
  }

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
    if (buildLog) buildLog.innerHTML = '<div class="log-line system">Build output will appear here...</div>';
  });
}

async function setupBugReporter() {
  const btnSubmit = document.getElementById('btn-submit-bug');
  if (!btnSubmit) return;

  btnSubmit.addEventListener('click', async () => {
    const discordName = document.getElementById('bug-discord-name').value.trim();
    if (!discordName) {
      alert("Please enter your Discord username.");
      return;
    }

    if (discordName.includes(' ')) {
      alert("Discord usernames/IDs cannot contain spaces.\nIf you are using your display name/nickname, please use your actual Discord username (which contains no spaces) or your 18-digit Discord User ID instead.");
      return;
    }

    const includeLog = document.getElementById('bug-include-log').checked;
    const includePack = document.getElementById('bug-include-pack').checked;
    const statusEl = document.getElementById('bug-report-status');

    statusEl.innerHTML = "Submitting bug report... <span class='status-spinner'>⏳</span>";
    statusEl.className = "status-hint";
    btnSubmit.disabled = true;

    let logPath = null;
    let packPath = null;
    let tempZipToClean = null;

    try {

      if (includeLog) {
        logPath = "patcher.log";
        const logContent = Array.from(document.querySelectorAll('.log-line')).map(el => el.innerText).join('\n');
        await invoke("write_text_file", { path: logPath, content: logContent });
      }



      if (includePack) {
        const mode = document.querySelector('input[name="patch-mode"]:checked').value;
        if (mode === 'zip') {
          packPath = document.getElementById('zip-input-file').value;
        } else if (mode === 'marketplace') {
          statusEl.innerHTML = "Zipping Marketplace Pack... <span class='status-spinner'>⏳</span>";
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
        packPath: packPath
      });

      if (res && res.success) {
        let msg = `✅ Bug Report submitted successfully! Case ID: #${res.caseId}`;
        if (res.replacedOld) {
            msg += `<br><br><span style="color: #fbbf24; font-size: 0.8rem;">Note: You already had a recent issue submitted. Your previous pack file has been replaced to save space.</span>`;
        }
        statusEl.innerHTML = msg;
        statusEl.className = "status-success";
      }

    } catch (err) {
      statusEl.innerHTML = `❌ Failed to submit: ${err}`;
      statusEl.className = "status-error";

      if (err.includes("User not found")) {
        showModal(err + "\nWould you like to join the Chaos dev project server now?", {
          title: "Join Server Required",
          confirm: true,
          okText: "Join Discord",
          cancelText: "Cancel"
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


// Check for Updates
async function checkForUpdates() {
  const badge = document.getElementById('update-badge');
  const btn = document.getElementById('btn-update-now');
  if (!badge) return;

  badge.className = "update-badge state-checking";
  badge.innerText = "Checking...";

  const allowBetaUpdates = localStorage.getItem('allow-beta-updates') === 'true';
  const isAdvanced = document.getElementById('chk-advanced-mode')?.checked;



  try {
    log("Checking for software updates...");
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
        log(`Software update v${userFacingVersion} is a Beta version, and Beta updates are disabled.`);
        badge.className = "update-badge state-uptodate";
        badge.innerText = "Up to Date";
        btn.classList.add('hidden-group');
        return;
      }

      // If alpha update but (beta updates are disabled OR advanced mode is disabled), ignore it
      if (isAlphaUpdate && (!allowBetaUpdates || !isAdvanced)) {
        log(`Software update v${userFacingVersion} is an Alpha version. It requires both Beta updates and Advanced Mode to be enabled.`);
        badge.className = "update-badge state-uptodate";
        badge.innerText = "Up to Date";
        btn.classList.add('hidden-group');
        return;
      }

      log(`New update available: v${userFacingVersion}`);
      badge.className = "update-badge state-available";
      badge.innerText = `v${userFacingVersion} Available`;
      btn.classList.remove('hidden-group');
      
      btn.onclick = async () => {
        // Confirmation dialog to never force beta updates
        let updateType = "Stable";
        if (isBetaUpdate) updateType = "Beta";
        else if (isAlphaUpdate) updateType = "Alpha";
        
        let message = `A new ${updateType} update (v${userFacingVersion}) is available.\n\nWould you like to download and install this update now?`;
        
        if (isAlphaUpdate) {
          message += `\n\n⚠️ WARNING ⚠️\nAlpha builds are highly unstable, completely untested, and might break your packs or fail entirely. Stuff will NOT work as expected! Proceed at your own risk!`;
        }

        const confirmed = await showConfirm(
          message,
          'Update Available'
        );
        if (!confirmed) return;

        btn.disabled = true;
        btn.innerText = "Updating...";
        log("Downloading and installing update...");
        try {
          if (!update.rid) {
            throw "Update metadata missing rid.";
          }
          
          const onEvent = new Channel();
          onEvent.onmessage = (event) => {
            if (event.event === "Progress") {
              const current = event.data.chunkLength || 0;
              log(`Downloading update: ${current} bytes...`);
            } else if (event.event === "Finished") {
              log("Download finished.");
            }
          };

          await invoke("plugin:updater|download_and_install", { 
            rid: update.rid,
            onEvent: onEvent
          });
          
          log("Update installed successfully. App will relaunch shortly.", "success");
          alert("Update installed successfully! The application will now restart.");
        } catch (err) {
          log(`Update installation failed: ${err}`, 'error');
          alert(`Update installation failed:\n${err}`);
          btn.disabled = false;
          btn.innerText = "Update Now";
        }
      };
    } else {
      log("Software is up to date.");
      badge.className = "update-badge state-uptodate";
      badge.innerText = "Up to Date";
      btn.classList.add('hidden-group');
    }
  } catch (err) {
    log(`Update check failed: ${err}`, 'warning');
    badge.className = "update-badge state-error";
    badge.innerText = "Check Failed";
    btn.classList.add('hidden-group');
  }
}

// App Settings State and Persistence
let appSettings = {
  defaultMode: 'marketplace',
  advancedMode: false,
  betaUpdates: false,
  cleanOld: true,
  extractBrarchives: false,
  genInjectManifest: true,
  genExtractBrarchives: false,
  genReplaceUnchanged: true,
  bugIncludeLog: true,
  bugIncludePack: false,
  sidebarCollapsed: false
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
  log("Initializing Actions & Stuff Patcher v3 Frontend...");

  // Load user settings
  await loadSettings();
  
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

  // Sync settings tabs to main UI tabs
  syncToggle('set-advanced-mode', 'chk-advanced-mode', 'advancedMode', true);
  syncToggle('set-beta-updates', 'chk-beta-updates', 'betaUpdates', true);
  syncToggle('set-clean-old', 'chk-clean-old', 'cleanOld');
  syncToggle('set-extract-brarchives', 'chk-extract-brarchives', 'extractBrarchives');
  syncToggle('set-gen-inject-manifest', 'gen-inject-manifest', 'genInjectManifest');
  syncToggle('set-gen-extract-brarchives', 'gen-extract-brarchives', 'genExtractBrarchives');
  syncToggle('set-gen-replace-unchanged', 'gen-replace-unchanged', 'genReplaceUnchanged');
  syncToggle('set-bug-include-log', 'bug-include-log', 'bugIncludeLog');
  syncToggle('set-bug-include-pack', 'bug-include-pack', 'bugIncludePack');

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
    resEl.textContent = 'Testing GitHub API...';
    try {
      const resp = await fetch('https://api.github.com/repos/Felix-Chaos/Actions-and-Stuff-RTX-Patcher/releases/latest');
      if (resp.ok) {
        const data = await resp.json();
        resEl.style.color = '#4ade80';
        resEl.textContent = `✅ Online. Latest release: ${data.tag_name}`;
      } else {
        resEl.style.color = '#ef4444';
        resEl.textContent = `❌ API returned status: ${resp.status}`;
      }
    } catch(e) {
      resEl.style.color = '#ef4444';
      resEl.textContent = `❌ Fetch failed: ${e.message}`;
    }
  });

  document.getElementById('btn-test-backend')?.addEventListener('click', async () => {
    const resEl = document.getElementById('api-test-results');
    if (!resEl) return;
    resEl.style.color = '#e2e8f0';
    resEl.textContent = 'Pinging Rust Backend...';
    try {
      const resp = await invoke("greet", { name: "Test" });
      resEl.style.color = '#4ade80';
      resEl.textContent = `✅ Rust backend is responding: ${resp}`;
    } catch(e) {
      resEl.style.color = '#ef4444';
      resEl.textContent = `❌ Backend error: ${e}`;
    }
  });

  document.getElementById('btn-test-workspace')?.addEventListener('click', async () => {
    const resEl = document.getElementById('api-test-results');
    if (!resEl) return;
    resEl.style.color = '#e2e8f0';
    resEl.textContent = 'Testing Workspace Paths...';
    try {
      const paths = await invoke("get_default_paths");
      const foundPath = paths.premium_cache || paths.mc_resource_packs || paths.premiumCache || paths.mcResourcePacks;
      resEl.style.color = '#4ade80';
      resEl.textContent = `✅ Found Workspace: ${foundPath || 'Unknown, check advanced options'}`;
    } catch(e) {
      resEl.style.color = '#ef4444';
      resEl.textContent = `❌ Workspace error: ${e}`;
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

  await loadPatchConfigs();
  await bindPickers();
  setupUtilities();
  setupReleaseBuilder();
  setupBugReporter();
  await loadMotd();
  await loadOptionsProfiles();
  log("System initialization complete. Ready.");
  
  // Hide release builder tab in non-dev builds
  try {
    const isDev = await invoke("is_dev_build");
    if (!isDev) {
      const releaseTab = document.querySelector('button[data-tab="release"]');
      if (releaseTab) {
        releaseTab.style.display = 'none';
      }
    }
  } catch (e) {
    console.error("Failed to check dev build status:", e);
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

