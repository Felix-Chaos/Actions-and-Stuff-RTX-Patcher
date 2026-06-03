// JavaScript Controller for Actions & Stuff RTX Patcher v3

// Destructure invoke and listen from Tauri Core
const { invoke } = window.__TAURI__ ? window.__TAURI__.core : { invoke: () => Promise.reject("Tauri not available") };
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

// Override window.alert with custom modal dialog to avoid exposing server IP
window.alert = function(msg) {
  const modal = document.getElementById('custom-modal');
  const messageEl = document.getElementById('modal-message');
  if (modal && messageEl) {
    messageEl.innerText = msg;
    modal.classList.remove('hidden-group');
  } else {
    console.warn("Custom alert modal: ", msg);
  }
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
      versionSelectGroup.classList.remove('hidden-group');
      if (zipFileGroup) zipFileGroup.classList.add('hidden-group');
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

function resolvePatchConfig(selectionMode, detectedVersion) {
  // Sort patchConfigs descending by packVersion and then by patchVersion
  const sortedConfigs = [...patchConfigs].sort((a, b) => {
    const verCompare = b.packVersion.localeCompare(a.packVersion, undefined, { numeric: true, sensitivity: 'base' });
    if (verCompare !== 0) return verCompare;
    const patchA = a.patchVersion || "1.0";
    const patchB = b.patchVersion || "1.0";
    return patchB.localeCompare(patchA, undefined, { numeric: true, sensitivity: 'base' });
  });

  if (selectionMode === 'auto') {
    if (detectedVersion && detectedVersion !== 'Unknown') {
      const match = sortedConfigs.find(c => c.packVersion === detectedVersion);
      if (match) return match;
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
      gLog_fn(`[3/4] Compressing patched target: ${patchedDir}`);
      const tgtZip = outputDir + "/_temp_target.zip";
      await invoke("pack_folder", { folderPath: patchedDir, outputZip: tgtZip });
      gLog_fn(`  ✓ Patched target ZIP ready`);

      // Step 4: Generate both patches
      gLog_fn(`[4/4] Generating VCDIFF patches...`);

      const encPatch = outputDir + "/encrypted.vcdiff";
      const decPatch = outputDir + "/decrypted.vcdiff";

      gLog_fn(`  Encoding encrypted.vcdiff (source: encrypted, target: patched)...`);
      await invoke("generate_xdelta_patch", { sourceFile: encZip, targetFile: tgtZip, patchFile: encPatch });
      gLog_fn(`  ✓ encrypted.vcdiff created`);

      gLog_fn(`  Encoding decrypted.vcdiff (source: decrypted, target: patched)...`);
      await invoke("generate_xdelta_patch", { sourceFile: decZip, targetFile: tgtZip, patchFile: decPatch });
      gLog_fn(`  ✓ decrypted.vcdiff created`);

      // Clean temp zips
      await invoke("delete_folders", { folders: [encZip, decZip, tgtZip] });

      gLog_fn(`✅ All patches created successfully in: ${outputDir}`, 'success');
      gLog_fn(`   Pack: ${packVer}  |  Patch: ${patchVer}`, 'success');

      // Open output folder in Explorer
      try { await invoke("open_in_explorer", { path: outputDir }); } catch (_) {}

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
      'gfx_rtx_resolution_scaling': { label: 'RTX Resolution Scale', type: 'percent' },
      'gfx_max_framerate': { label: 'Max Framerate', type: 'number' },
      'gfx_vsync': { label: 'VSync', type: 'bool' }
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
        const sel = document.createElement('select');
        sel.dataset.key = key;
        sel.innerHTML = `
          <option value="1" ${val == '1' ? 'selected' : ''}>On / True</option>
          <option value="0" ${val == '0' ? 'selected' : ''}>Off / False</option>
        `;
        controlDiv.appendChild(sel);
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
  } catch (err) {
    log(`Failed to read options: ${err}`, 'error');
  }
}

document.getElementById('btn-save-settings').addEventListener('click', async () => {
  if (!selectedOptionsPath) return;
  
  const controls = document.querySelectorAll('.option-control select, .option-control input');
  const changes = {};
  controls.forEach(ctrl => {
    changes[ctrl.dataset.key] = ctrl.value;
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
  if (!confirm(`Are you sure you want to delete all ${cleanablePacksPaths.length} located folders?`)) {
    return;
  }
  
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
      const candidates = await invoke("scan_marketplace_packs");
      log(`Found ${candidates.length} candidate packs in premium cache.`);
      
      candidates.forEach((cand, idx) => {
        log(`Candidate [${idx + 1}]:`);
        log(`  Folder Name: ${cand.folder_name}`);
        log(`  Full Path:   ${cand.path}`);
        log(`  Version:     ${cand.version}`);
        log(`  Contents:    ${cand.files_count} files, ${cand.dirs_count} directories`);
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
        
        patchConfigToUse = resolvePatchConfig(selectionMode, best.version);
        if (selectionMode === 'manual' && patchConfigToUse.packVersion !== best.version) {
          log(`Warning: Target patch version (${patchConfigToUse.packVersion}) does not match detected pack version (${best.version}).`, 'warning');
          if (!confirm(`Warning: The selected patch version (${patchConfigToUse.packVersion}) differs from your installed pack version (${best.version}).\n\nDo you want to proceed anyway?`)) {
            throw "User aborted due to version mismatch.";
          }
        }
      }
      
      updateStepState(0, 'completed');
      
      // STEP 1: COMPRESSION / NORMALIZATION
      updateStepState(1, 'active');
      
      const sourcePackPath = candidates.length > 0 ? candidates[0].path : document.getElementById('custom-src').value;
      const zipOut = `${sourcePackPath}_vanilla.zip`;
      let targetFolder = sourcePackPath;
 
      if (extractBrarchives) {
        updateStatus("Extracting Brarchives (Beta)", "Copying and extracting brarchives...", '📦');
        updateProgress(15);
        targetFolder = `${sourcePackPath}_mp_extracted`;
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
      
      const tempExtract = `${selectedZip}_extracted`;
      log(`Extracting ZIP file to temp directory:`);
      log(`  Source ZIP: "${selectedZip}"`);
      log(`  Target Dir: "${tempExtract}"`);
      await invoke("extract_archive", { zipPath: selectedZip, outputDir: tempExtract });
      log("ZIP extraction completed successfully.");
      
      log("Normalizing contents: deleting license signatures (contents.json, signatures.json, splashes.json, sounds.json, texts/) and injecting custom manifest...");
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
      
      const normalizedZip = `${selectedZip}_normalized.zip`;
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
        if (extractBrarchives) {
          updateStatus("Extracting Brarchives (Beta)", "Extracting brarchives inside custom source ZIP...", '📦');
          updateProgress(15);
          const tempExtract = `${src}_custom_extracted`;
          log(`Extracting custom source ZIP: "${src}" to "${tempExtract}"`);
          await invoke("extract_archive", { zipPath: src, outputDir: tempExtract });
          log(`Extracting brarchives recursively inside: "${tempExtract}"`);
          await invoke("extract_brarchives_in_workspace", { workspace: tempExtract });
          const customZip = `${src}_custom_source.zip`;
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
        if (extractBrarchives) {
          updateStatus("Extracting Brarchives (Beta)", "Copying and extracting custom brarchives...", '📦');
          updateProgress(15);
          const targetFolder = `${src}_custom_staged`;
          log(`Staging custom source folder to Extract Brarchives:`);
          log(`  Staging Source: "${src}"`);
          log(`  Staging Target: "${targetFolder}"`);
          await invoke("stage_and_extract_brarchives", { sourceDir: src, tempDir: targetFolder });
          const customZip = `${src}_custom_source.zip`;
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
          const customZip = `${src}_custom_source.zip`;
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
    if (mode === 'marketplace' || (mode === 'custom' && !document.getElementById('custom-src').value.endsWith('.zip'))) {
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
  } finally {
    document.getElementById('btn-start-patch').disabled = false;
  }
});

document.getElementById('btn-install-pack').addEventListener('click', async () => {
  if (!finalPatchedPath) return;
  try {
    log(`Launching installer for: ${finalPatchedPath}`);
    const actualMcpack = await invoke("install_mcpack", { outputFile: finalPatchedPath });
    log(`Minecraft launched. Registered pack as: ${actualMcpack}`, 'success');
    updateStepState(4, 'completed');
    document.getElementById('btn-install-pack').classList.add('hidden-group');
  } catch (err) {
    log(`Install failed: ${err}`, 'error');
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
});

// Back to Selection Button
document.getElementById('btn-patch-back').addEventListener('click', () => {
  document.querySelector('.progress-panel').classList.add('hidden-group');
  document.querySelector('.controls-panel').classList.remove('hidden-group');
  updateStatus("Ready to Patch", "Configure options and click Apply", '💤');
  updateProgress(0);
  resetSteps();
});

// Copy Console Log
const btnCopyLog = document.getElementById('btn-copy-log');
if (btnCopyLog) btnCopyLog.addEventListener('click', () => copyLogsFromEl('console-logs', 'btn-copy-log'));
const btnCopyLogLarge = document.getElementById('btn-copy-log-large');
if (btnCopyLogLarge) btnCopyLogLarge.addEventListener('click', () => copyLogsFromEl('console-logs', 'btn-copy-log-large'));
document.getElementById('btn-clear-console').addEventListener('click', clearConsole);

function parseVersion(verStr) {
  const isBeta = verStr.endsWith('_b') || verStr.endsWith('-b') || verStr.endsWith('-0');
  const cleanVer = verStr.endsWith('_b') ? verStr.slice(0, -2) : (verStr.endsWith('-b') ? verStr.slice(0, -2) : (verStr.endsWith('-0') ? verStr.slice(0, -2) : verStr));
  const parts = cleanVer.split('.').map(Number);
  return {
    major: isNaN(parts[0]) ? 0 : parts[0],
    minor: isNaN(parts[1]) ? 0 : parts[1],
    patch: isNaN(parts[2]) ? 0 : parts[2],
    isBeta: isBeta
  };
}

function formatVersion(parsed) {
  return `${parsed.major}.${parsed.minor}.${parsed.patch}${parsed.isBeta ? '_b' : ''}`;
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
  const chkIsBeta = document.getElementById('chk-is-beta-ver');

  const updateVerInputs = (parsed) => {
    if (relVerInput) {
      relVerInput.value = formatVersion(parsed);
    }
    if (chkIsBeta) {
      chkIsBeta.checked = parsed.isBeta;
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

  // Beta checkbox listener
  chkIsBeta?.addEventListener('change', (e) => {
    if (!relVerInput) return;
    const parsed = parseVersion(relVerInput.value);
    parsed.isBeta = e.target.checked;
    updateVerInputs(parsed);
  });

  // Apply version button — writes to tauri.conf.json
  const btnApplyVer = document.getElementById('btn-apply-version');
  if (btnApplyVer) {
    btnApplyVer.addEventListener('click', async () => {
      const newVer = relVerInput ? relVerInput.value.trim() : '';
      if (!newVer) { alert("Please enter a version number."); return; }
      const pingNeeded = document.getElementById('chk-ping-needed') ? document.getElementById('chk-ping-needed').checked : true;
      try {
        await invoke("update_app_version", { version: newVer, pingEveryone: pingNeeded });
        if (relHint) relHint.innerText = `Current: v${newVer} (saved)`;
        if (versionBadge) versionBadge.innerText = `v${newVer}`;
      } catch (err) {
        bLog(`Failed to update app version: ${err}`, 'error');
        alert(`Failed to update app version:\n${err}`);
      }
    });
  }

  // Build Release
  const btnBuild = document.getElementById('btn-build-release');
  if (btnBuild) {
    btnBuild.addEventListener('click', async () => {
      buildLog.innerHTML = '<div class="log-line system">Starting release build...</div>';
      btnBuild.disabled = true;
      try {
        await invoke("run_release_build");
      } catch (err) {
        bLog(`Failed to run release build: ${err}`, 'error');
        alert(`Failed to run release build:\n${err}`);
      } finally {
        btnBuild.disabled = false;
      }
    });
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

  // Copy/Clear build log
  const btnCopyBuild = document.getElementById('btn-copy-build-log');
  if (btnCopyBuild) btnCopyBuild.addEventListener('click', () => copyLogsFromEl('build-logs', 'btn-copy-build-log'));
  const btnClearBuild = document.getElementById('btn-clear-build-log');
  if (btnClearBuild) btnClearBuild.addEventListener('click', () => {
    if (buildLog) buildLog.innerHTML = '<div class="log-line system">Build output will appear here...</div>';
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

  try {
    log("Checking for software updates...");
    const update = await invoke("plugin:updater|check");
    
    if (update && update.version) {
      const isBetaUpdate = update.version.endsWith('_b') || update.version.endsWith('-b') || update.version.endsWith('-0');
      const userFacingVersion = update.version.replace('-b', '_b').replace('-0', '_b');
      
      // If beta update but beta updates are disabled, ignore it
      if (isBetaUpdate && !allowBetaUpdates) {
        log(`Software update v${userFacingVersion} is a Beta version, and Beta updates are disabled.`);
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
        const updateType = isBetaUpdate ? "Beta" : "Stable";
        if (!confirm(`A new ${updateType} update (v${userFacingVersion}) is available.\n\nWould you like to download and install this update now?`)) {
          return;
        }

        btn.disabled = true;
        btn.innerText = "Updating...";
        log("Downloading and installing update...");
        try {
          await invoke("plugin:updater|download_and_install");
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

// Initialize everything on page load
window.addEventListener('DOMContentLoaded', async () => {
  log("Initializing Actions & Stuff Patcher v3 Frontend...");

  // Dynamically set version badge from backend/tauri.conf.json
  try {
    let appVersion = await invoke("get_app_version");
    appVersion = appVersion.replace("-b", "_b").replace("-0", "_b");
    const versionBadge = document.getElementById('app-version-badge');
    if (versionBadge) {
      versionBadge.innerText = `v${appVersion}`;
    }
  } catch (e) {
    console.error("Failed to load app version:", e);
  }

  await loadPatchConfigs();
  await bindPickers();
  setupUtilities();
  setupReleaseBuilder();
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

  // Wire OK button for custom alert modal
  const btnModalOk = document.getElementById('btn-modal-ok');
  const customModal = document.getElementById('custom-modal');
  if (btnModalOk && customModal) {
    btnModalOk.addEventListener('click', () => {
      customModal.classList.add('hidden-group');
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
