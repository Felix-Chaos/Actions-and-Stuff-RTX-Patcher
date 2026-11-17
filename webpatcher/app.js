// Web Patcher UI: find the A&S pack in the picked folder, choose the matching
// patch from the Patch Library, hand the work to worker.js.
// Mirrors the desktop patcher's Marketplace mode (scan_marketplace_packs,
// resolvePatchConfig, pack_folder + run_xdelta_patch with encrypted.vcdiff).

const LIBRARY = (() => {
  const real = "https://raw.githubusercontent.com/Felix-Chaos/AS-RTX-Patch-Library/main";
  // Local testing only: ?library=<url> on localhost swaps in a test catalogue.
  const local = ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
  const override = local && new URLSearchParams(location.search).get("library");
  return override ? new URL(override, location.href).href.replace(/\/$/, "") : real;
})();
const AS_UUID = "22ed17a6-ea7c-5ccd-93b4-b90e86ce0046";
const LANG_FILES = ["texts/en_US.lang", "texts/en_US.txt", "en_US.lang", "en_US.txt"];

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// "v1.11.0" and "1.11" name the same pack version.
const normVer = (v) => {
  const parts = String(v || "").trim().replace(/^v/i, "").split(".");
  while (parts.length > 1 && /^0+$/.test(parts[parts.length - 1])) parts.pop();
  return parts.join(".");
};
const cmpNum = (a, b) => String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
const isBeta = (e) => (typeof e.beta === "boolean" ? e.beta : /^v?0(\.|$)/i.test(String(e.patchVersion)));
const mb = (n) => (n / 1048576).toFixed(n < 10485760 ? 1 : 0) + " MB";

// Locked browsers only see the "not open yet" card (see unlock.js).
const unlocked = await (window.rtxWebPatcherUnlocked || Promise.resolve(false));
$("locked").hidden = unlocked;
$("steps").hidden = !unlocked;

let indexPromise = null;
const loadIndex = () =>
  (indexPromise ||= fetch(`${LIBRARY}/patch_index.json`, { cache: "no-cache" })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`Patch list: HTTP ${r.status}`))))
    .then((d) =>
      (d.entries || [])
        .filter((e) => e.patches && e.patches.encrypted)
        .sort((a, b) => cmpNum(b.packVersion, a.packVersion) || cmpNum(b.patchVersion || "1.0", a.patchVersion || "1.0"))
    ));
if (unlocked) loadIndex().catch(() => {}); // warm up while the user picks the folder

let pack = null; // detected candidate
let entries = [];
let chosen = null;

// ---------- folder scan ----------

async function sha256Hex(blob) {
  const d = new Uint8Array(await crypto.subtle.digest("SHA-256", await blob.arrayBuffer()));
  return Array.from(d, (b) => b.toString(16).padStart(2, "0")).join("");
}

// Same parsing as get_pack_name_version in the desktop patcher.
function langVersion(text) {
  for (const line of text.split(/\r?\n/)) {
    if (!line.startsWith("pack.name=")) continue;
    const i = line.indexOf("Actions & Stuf");
    if (i < 0) continue;
    const v = line.slice(i + 14).replace(/[^0-9.]/g, "").replace(/^\.+|\.+$/g, "");
    if (v) return v;
  }
  return null;
}

async function describePack(root, files) {
  const byPath = new Map(files.map((f) => [f.path, f.file]));
  let isAS = false;
  let version = null;
  for (const p of LANG_FILES) {
    const f = byPath.get(p);
    if (!f) continue;
    const text = await f.text();
    if (text.split(/\r?\n/).some((l) => l.startsWith("pack.name=") && l.includes("Actions & Stuf"))) isAS = true;
    if (!version && p === "texts/en_US.lang") version = langVersion(text);
  }
  const manifest = byPath.get("manifest.json");
  if (manifest) {
    const text = await manifest.text();
    if (text.includes(AS_UUID)) isAS = true;
    if (!version && byPath.has("texts/en_US.lang")) {
      try {
        const v = JSON.parse(text).header.version;
        version = Array.isArray(v) ? v.join(".") : typeof v === "string" ? v : null;
      } catch (_) {}
    }
  }
  const dirs = new Set();
  for (const f of files) {
    const parts = f.path.split("/");
    for (let i = 1; i < parts.length; i++) dirs.add(parts.slice(0, i).join("/"));
  }
  const icon = byPath.get("pack_icon.png");
  return {
    root,
    files,
    isAS,
    version,
    filesCount: files.length,
    dirsCount: dirs.size,
    size: files.reduce((s, f) => s + f.file.size, 0),
    logoHash: icon ? await sha256Hex(icon) : null,
  };
}

// Every folder holding a manifest.json is a pack; nested ones belong to their parent.
function splitPacks(fileList) {
  const all = Array.from(fileList, (file) => {
    const rel = (file.webkitRelativePath || file.name).split("/");
    return { segs: rel.slice(1), file }; // drop the picked folder's own name
  });
  const roots = new Set();
  for (const f of all) {
    if (f.segs[f.segs.length - 1] === "manifest.json") roots.add(f.segs.slice(0, -1).join("/"));
  }
  const sorted = [...roots].sort((a, b) => a.length - b.length);
  const top = sorted.filter((r) => !sorted.some((o) => o !== r && (o === "" || r.startsWith(o + "/"))));
  return top.map((root) => {
    const prefix = root ? root + "/" : "";
    const files = all
      .map((f) => ({ full: f.segs.join("/"), file: f.file }))
      .filter((f) => f.full.startsWith(prefix))
      .map((f) => ({ path: f.full.slice(prefix.length), file: f.file }));
    return { root, files };
  });
}

// resolvePatchConfig's "solid hit": logo hash and file count (dirs are skipped:
// browsers do not report empty folders, so the count can differ).
function fits(entry, cand) {
  const valid = entry.validation || {};
  const stats = entry.stats || entry.marketplace_pack_stats?.v1 || {};
  const hashOk = !(valid.logo_hash && cand.logoHash) || valid.logo_hash === cand.logoHash;
  const filesOk = !stats.files || Math.abs(stats.files - cand.filesCount) <= 5;
  return Boolean(valid.logo_hash || stats.files) && hashOk && filesOk;
}

function sameVersion(entry, cand) {
  return cand.version && normVer(entry.packVersion) === normVer(cand.version);
}

// ---------- UI ----------

function unlock(id, on) {
  $(id).classList.toggle("is-locked", !on);
}

function setResult(html, kind = "") {
  const el = $("pack-result");
  el.hidden = false;
  el.className = "wp-result" + (kind ? " wp-result--" + kind : "");
  el.innerHTML = html;
}

$("folder").addEventListener("change", async (ev) => {
  const list = ev.target.files;
  resetRun();
  pack = null;
  chosen = null;
  unlock("step-patch", false);
  unlock("step-run", false);
  $("start").disabled = true;
  if (!list || list.length === 0) return;

  setResult(`Looking at ${list.length} files…`);
  try {
    const packs = splitPacks(list);
    const described = [];
    for (const p of packs) described.push(await describePack(p.root, p.files));
    const candidates = described.filter((d) => d.isAS);
    if (candidates.length === 0) {
      setResult(
        packs.length
          ? `No Actions &amp; Stuff pack in this folder (found ${packs.length} other pack${packs.length > 1 ? "s" : ""}). Did you pick <code>premium_cache\\resource_packs</code>?`
          : "This folder contains no resource packs. Pick <code>premium_cache\\resource_packs</code>.",
        "warn"
      );
      return;
    }

    try {
      entries = await loadIndex();
    } catch (err) {
      indexPromise = null;
      setResult(`Could not load the patch list: ${esc(err.message)}. Check your connection and pick the folder again.`, "warn");
      return;
    }

    // Prefer the pack a patch fits exactly, then one whose version has a patch.
    const rank = (c) => (entries.some((e) => fits(e, c)) ? 2 : entries.some((e) => sameVersion(e, c)) ? 1 : 0);
    candidates.sort((a, b) => rank(b) - rank(a) || b.filesCount - a.filesCount);
    pack = candidates[0];

    setResult(
      `Found <strong>Actions &amp; Stuff ${esc(pack.version || "(unknown version)")}</strong>` +
        ` · ${pack.filesCount} files · ${mb(pack.size)}` +
        (candidates.length > 1 ? `<br><span class="wp-muted">${candidates.length} A&amp;S copies found, using the one that fits a patch best.</span>` : ""),
      "ok"
    );
    renderPatchChoice();
  } catch (err) {
    setResult(`Could not read the folder: ${esc(err.message)}`, "warn");
  }
});

function renderPatchChoice() {
  const box = $("patch-box");
  unlock("step-patch", true);
  const fitting = entries.filter((e) => fits(e, pack));
  const versionOnly = entries.filter((e) => !fits(e, pack) && sameVersion(e, pack));
  const recommended = fitting.find((e) => !isBeta(e)) || fitting[0] || versionOnly.find((e) => !isBeta(e)) || versionOnly[0];

  if (!recommended) {
    const newest = entries[0];
    box.innerHTML =
      `<div class="disclaimer-box disclaimer-box--warn"><span>There is no RTX patch for <strong>A&amp;S ${esc(pack.version || "this version")}</strong> yet` +
      (newest ? ` (newest patch: A&amp;S ${esc(normVer(newest.packVersion))})` : "") +
      `. <a href="../uptodate/">Is A&amp;S RTX up to date?</a></span></div>`;
    unlock("step-run", false);
    $("start").disabled = true;
    return;
  }

  const label = (e) =>
    `A&S ${normVer(e.packVersion)} · Patch ${e.patchVersion || "1.0"}` +
    (isBeta(e) ? " · Beta" : "") +
    (e.hotpatch ? " · Hotpatch" : "") +
    (fits(e, pack) || sameVersion(e, pack) ? "" : " · other A&S version!");
  const opts = entries
    .map((e) => `<option value="${esc(e.slug)}"${e === recommended ? " selected" : ""}>${esc(label(e))}</option>`)
    .join("");
  box.innerHTML =
    `<label class="field-label" for="patch-select">Patch to apply</label>` +
    `<select id="patch-select" class="wp-select">${opts}</select>` +
    `<p class="status-hint" id="patch-hint"></p>`;
  const sel = $("patch-select");
  const update = () => {
    chosen = entries.find((e) => e.slug === sel.value);
    const ok = fits(chosen, pack) || sameVersion(chosen, pack);
    $("patch-hint").textContent = ok
      ? `Fits your pack · download ${mb(chosen.patches.encrypted.size || 0)}`
      : `Made for A&S ${normVer(chosen.packVersion)}, your pack is ${pack.version || "unknown"}: this will most likely fail.`;
    $("patch-hint").classList.toggle("wp-warn-text", !ok);
    resetRun();
  };
  sel.addEventListener("change", update);
  update();
  unlock("step-run", true);
  $("start").disabled = false;
}

// ---------- run ----------

let worker = null;
let resultUrl = null;

function resetRun() {
  if (worker) {
    worker.terminate();
    worker = null;
  }
  if (resultUrl) {
    URL.revokeObjectURL(resultUrl);
    resultUrl = null;
  }
  $("progress").hidden = true;
  $("bar").hidden = true;
  $("error").hidden = true;
  $("done").hidden = true;
  $("start").hidden = false;
  $("start").disabled = !chosen;
  $("folder").disabled = false;
  for (const li of $("progress").children) {
    li.className = "";
    li.querySelector(".wp-progress__val").textContent = "";
  }
}

const STEPS = ["zip", "download", "verify", "apply"];

function markStep(step) {
  const idx = STEPS.indexOf(step);
  for (const li of $("progress").children) {
    const i = STEPS.indexOf(li.dataset.step);
    li.className = i < idx ? "is-done" : i === idx ? "is-active" : "";
    if (i < idx) li.querySelector(".wp-progress__val").textContent = "✓";
  }
  setBar(0);
}

function setBar(frac) {
  $("bar").firstElementChild.style.width = `${Math.round(Math.min(1, Math.max(0, frac)) * 100)}%`;
}

$("start").addEventListener("click", () => {
  if (!pack || !chosen) return;
  resetRun();
  $("start").hidden = true;
  $("folder").disabled = true;
  $("progress").hidden = false;
  $("bar").hidden = false;

  const enc = chosen.patches.encrypted;
  const folder = chosen.folder_name.split("/").map(encodeURIComponent).join("/");
  const patch = { url: `${LIBRARY}/Patches/${folder}/encrypted.vcdiff`, sha256: enc.sha256, size: enc.size };
  const outName = `Actions & Stuff RTX ${normVer(chosen.packVersion)} P${chosen.patchVersion || "1.0"}.mcpack`;

  worker = new Worker(new URL("worker.js?v=20261116", import.meta.url), { type: "module" });
  worker.onmessage = (ev) => {
    const m = ev.data;
    if (m.type === "step") markStep(m.step);
    else if (m.type === "progress") {
      setBar(m.total ? m.done / m.total : 0);
      const li = $("progress").querySelector(`[data-step="${m.step}"] .wp-progress__val`);
      if (li && (m.step === "zip" || m.step === "download")) li.textContent = `${mb(m.done)} / ${mb(m.total)}`;
      else if (li) li.textContent = `${Math.round((m.done / m.total) * 100)}%`;
    } else if (m.type === "done") {
      for (const li of $("progress").children) {
        li.className = "is-done";
        li.querySelector(".wp-progress__val").textContent = "✓";
      }
      setBar(1);
      resultUrl = URL.createObjectURL(m.result);
      const a = $("save");
      a.href = resultUrl;
      a.download = outName;
      a.textContent = `Download .mcpack (${mb(m.result.size)})`;
      $("done").hidden = false;
      $("folder").disabled = false;
      worker.terminate();
      worker = null;
    } else if (m.type === "error") {
      fail(m.message);
    }
  };
  worker.onerror = (e) => fail(e.message || "The patch worker crashed (out of memory?)");
  worker.postMessage({ files: pack.files, patch });
});

function fail(message) {
  if (worker) {
    worker.terminate();
    worker = null;
  }
  const el = $("error");
  el.hidden = false;
  el.innerHTML =
    `<span><strong>Patching failed:</strong> ${esc(message)}<br>` +
    `Make sure Minecraft has fully downloaded A&amp;S and the pack is unmodified, then try again. ` +
    `Still stuck? Ask in the <a href="https://discord.gg/55nhtqdmYD" rel="noopener">Discord</a>.</span>`;
  const active = $("progress").querySelector(".is-active");
  if (active) active.className = "is-failed";
  $("start").hidden = false;
  $("start").disabled = false;
  $("start").textContent = "Try again";
  $("folder").disabled = false;
}

// ---------- copy buttons ----------

document.querySelectorAll("[data-copy]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const text = $(btn.dataset.copy).textContent;
    try {
      await navigator.clipboard.writeText(text);
      btn.textContent = "Copied";
    } catch (_) {
      const r = document.createRange();
      r.selectNodeContents($(btn.dataset.copy));
      getSelection().removeAllRanges();
      getSelection().addRange(r);
      btn.textContent = "Ctrl+C";
    }
    setTimeout(() => (btn.textContent = "Copy"), 1500);
  });
});
