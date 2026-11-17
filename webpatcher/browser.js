// Web Patcher, "Browser only" mode (beta, Chrome/Edge): no helper program.
//
// 1. The A&S folder is read through a classic folder upload (webkitdirectory),
//    which may read premium_cache; nothing is uploaded anywhere.
// 2. worker.js zips it exactly like the desktop patcher and applies the
//    encrypted.vcdiff from the Patch Library.
// 3. The result is written as a .mcpack into C:\Users\Public\Documents (the one
//    folder with the same path on every PC, which Chrome lets sites write to),
//    Minecraft imports it from there through minecraft://?importpack=<path>,
//    and the page deletes the temporary .mcpack again.
// Chrome blocks every folder below %APPDATA% for websites, so writing straight
// into resource_packs is not possible; that is what the helper mode is for.

const LIBRARY = (() => {
  const real = "https://raw.githubusercontent.com/Felix-Chaos/AS-RTX-Patch-Library/main";
  const local = ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
  const override = local && new URLSearchParams(location.search).get("library");
  return override ? new URL(override, location.href).href.replace(/\/$/, "") : real;
})();
const AS_UUID = "22ed17a6-ea7c-5ccd-93b4-b90e86ce0046";
const LANG_FILES = ["texts/en_US.lang", "texts/en_US.txt", "en_US.lang", "en_US.txt"];
const DROP_DIR = "C:\\Users\\Public\\Documents";
const DROP_PREFIX = "asrtx-import-";
// Deleting the .mcpack while Minecraft still reads it would break the import.
const AUTO_CLEANUP_MS = 60000;

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const normVer = (v) => {
  const parts = String(v || "").trim().replace(/^v/i, "").split(".");
  while (parts.length > 1 && /^0+$/.test(parts[parts.length - 1])) parts.pop();
  return parts.join(".");
};
const cmpNum = (a, b) => String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
const isBeta = (e) => (typeof e.beta === "boolean" ? e.beta : /^v?0(\.|$)/i.test(String(e.patchVersion)));
const mb = (n) => (n / 1048576).toFixed(n < 10485760 ? 1 : 0) + " MB";
const supported = typeof window.showDirectoryPicker === "function";

const unlocked = await (window.rtxWebPatcherUnlocked || Promise.resolve(false));

// ---------- mode switch ----------

const MODE_KEY = "asrtx-webpatcher-mode";
function setMode(mode) {
  if (mode === "browser" && !supported) mode = "helper";
  $("steps").hidden = mode !== "helper";
  $("steps-browser").hidden = mode !== "browser";
  for (const b of document.querySelectorAll("[data-mode]")) b.setAttribute("aria-pressed", String(b.dataset.mode === mode));
  try {
    localStorage.setItem(MODE_KEY, mode);
  } catch (_) {}
}
for (const b of document.querySelectorAll("[data-mode]")) b.addEventListener("click", () => setMode(b.dataset.mode));
if (!supported) {
  const b = document.querySelector('[data-mode="browser"]');
  b.disabled = true;
  b.title = "Chrome or Edge only";
  $("mode-note").hidden = false;
}
let saved = "helper";
try {
  saved = localStorage.getItem(MODE_KEY) || "helper";
} catch (_) {}
setMode(saved);

// ---------- catalogue ----------

let indexPromise = null;
const loadIndex = () =>
  (indexPromise ||= fetch(`${LIBRARY}/patch_index.json`, { cache: "no-cache" })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`Patch list: HTTP ${r.status}`))))
    .then((d) =>
      (d.entries || [])
        .filter((e) => e.patches && e.patches.encrypted)
        .sort((a, b) => cmpNum(b.packVersion, a.packVersion) || cmpNum(b.patchVersion || "1.0", a.patchVersion || "1.0"))
    ));

let pack = null;
let entries = [];
let chosen = null;
let dropDir = null;
let worker = null;
let pending = null; // { name, launchedAt } of the .mcpack waiting in the drop folder

// ---------- folder scan (same rules as the desktop patcher) ----------

async function sha256Hex(blob) {
  const d = new Uint8Array(await crypto.subtle.digest("SHA-256", await blob.arrayBuffer()));
  return Array.from(d, (b) => b.toString(16).padStart(2, "0")).join("");
}

function langVersion(text) {
  for (const line of text.split(/\r?\n/)) {
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
  const icon = byPath.get("pack_icon.png");
  return {
    root,
    files,
    isAS,
    version,
    count: files.length,
    size: files.reduce((s, f) => s + f.file.size, 0),
    logoHash: icon ? await sha256Hex(icon) : null,
  };
}

function splitPacks(fileList) {
  const all = Array.from(fileList, (file) => {
    const rel = (file.webkitRelativePath || file.name).split("/");
    return { segs: rel.slice(1), file };
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

function fits(entry, cand) {
  const valid = entry.validation || {};
  const stats = entry.stats || entry.marketplace_pack_stats?.v1 || {};
  const hashOk = !(valid.logo_hash && cand.logoHash) || valid.logo_hash === cand.logoHash;
  const filesOk = !stats.files || Math.abs(stats.files - cand.count) <= 5;
  return Boolean(valid.logo_hash || stats.files) && hashOk && filesOk;
}
const sameVersion = (entry, cand) => cand.version && normVer(entry.packVersion) === normVer(cand.version);

// ---------- UI ----------

const unlock = (id, on) => $(id).classList.toggle("is-locked", !on);
function setResult(id, html, kind = "") {
  const el = $(id);
  el.hidden = false;
  el.className = "wp-result" + (kind ? " wp-result--" + kind : "");
  el.innerHTML = html;
}
function updateStart() {
  $("b-start").disabled = !(pack && chosen && dropDir) || Boolean(worker);
}

$("b-folder").addEventListener("change", async (ev) => {
  const list = ev.target.files;
  resetRun();
  pack = null;
  chosen = null;
  $("b-patch-box").innerHTML = `<p class="wp-hint">Choose your A&amp;S folder first.</p>`;
  updateStart();
  if (!list || list.length === 0) return;

  setResult("b-pack-result", `Looking at ${list.length} files…`);
  try {
    const packs = splitPacks(list);
    const described = [];
    for (const p of packs) described.push(await describePack(p.root, p.files));
    const candidates = described.filter((d) => d.isAS);
    if (candidates.length === 0) {
      setResult(
        "b-pack-result",
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
      setResult("b-pack-result", `Could not load the patch list: ${esc(err.message)}. Check your connection and pick the folder again.`, "warn");
      return;
    }
    const rank = (c) => (entries.some((e) => fits(e, c)) ? 2 : entries.some((e) => sameVersion(e, c)) ? 1 : 0);
    candidates.sort((a, b) => rank(b) - rank(a) || b.count - a.count);
    pack = candidates[0];
    setResult(
      "b-pack-result",
      `Found <strong>Actions &amp; Stuff ${esc(pack.version || "(unknown version)")}</strong> · ${pack.count} files · ${mb(pack.size)}` +
        (candidates.length > 1 ? `<br><span class="wp-muted">${candidates.length} A&amp;S copies found, using the one that fits a patch best.</span>` : ""),
      "ok"
    );
    renderPatchChoice();
  } catch (err) {
    setResult("b-pack-result", `Could not read the folder: ${esc(err.message)}`, "warn");
  }
});

function renderPatchChoice() {
  const box = $("b-patch-box");
  const fitting = entries.filter((e) => fits(e, pack));
  const versionOnly = entries.filter((e) => !fits(e, pack) && sameVersion(e, pack));
  const recommended = fitting.find((e) => !isBeta(e)) || fitting[0] || versionOnly.find((e) => !isBeta(e)) || versionOnly[0];
  if (!recommended) {
    const newest = entries[0];
    box.innerHTML =
      `<div class="disclaimer-box disclaimer-box--warn"><span>There is no RTX patch for <strong>A&amp;S ${esc(pack.version || "this version")}</strong> yet` +
      (newest ? ` (newest patch: A&amp;S ${esc(normVer(newest.packVersion))})` : "") +
      `. <a href="../uptodate/">Is A&amp;S RTX up to date?</a></span></div>`;
    chosen = null;
    updateStart();
    return;
  }
  const label = (e) =>
    `A&S ${normVer(e.packVersion)} · Patch ${e.patchVersion || "1.0"}` +
    (isBeta(e) ? " · Beta" : "") +
    (e.hotpatch ? " · Hotpatch" : "") +
    (fits(e, pack) || sameVersion(e, pack) ? "" : " · other A&S version!");
  box.innerHTML =
    `<label class="field-label" for="b-patch-select">Patch to apply</label>` +
    `<select id="b-patch-select" class="wp-select">${entries
      .map((e) => `<option value="${esc(e.slug)}"${e === recommended ? " selected" : ""}>${esc(label(e))}</option>`)
      .join("")}</select>` +
    `<p class="status-hint" id="b-patch-hint"></p>`;
  const sel = $("b-patch-select");
  const update = () => {
    chosen = entries.find((e) => e.slug === sel.value);
    const ok = fits(chosen, pack) || sameVersion(chosen, pack);
    $("b-patch-hint").textContent = ok
      ? `Fits your pack · download ${mb(chosen.patches.encrypted.size || 0)}`
      : `Made for A&S ${normVer(chosen.packVersion)}, your pack is ${pack.version || "unknown"}: this will most likely fail.`;
    $("b-patch-hint").classList.toggle("wp-warn-text", !ok);
    resetRun();
    updateStart();
  };
  sel.addEventListener("change", update);
  update();
}

// ---------- hand-over folder ----------

$("b-drop").addEventListener("click", async () => {
  try {
    const dir = await window.showDirectoryPicker({ id: "asrtx-import", mode: "readwrite", startIn: "documents" });
    // The path itself is hidden from websites, so only the name can be checked.
    if (dir.name !== "Documents") {
      setResult("b-drop-result", `That folder is called <code>${esc(dir.name)}</code>. Please pick <code>${DROP_DIR}</code>.`, "warn");
      return;
    }
    dropDir = dir;
    const stale = await removeStale();
    setResult(
      "b-drop-result",
      `Using <code>${DROP_DIR}</code>.` +
        (stale ? ` <span class="wp-muted">Removed ${stale} leftover file${stale > 1 ? "s" : ""} from an earlier run.</span>` : "") +
        `<br><span class="wp-muted">Picked your own Documents instead? Then Minecraft cannot find the file; pick the public one.</span>`,
      "ok"
    );
    updateStart();
  } catch (err) {
    if (err.name !== "AbortError") setResult("b-drop-result", `Could not open the folder: ${esc(err.message)}`, "warn");
  }
});

async function removeStale() {
  let n = 0;
  for await (const [name, h] of dropDir.entries()) {
    if (h.kind === "file" && name.startsWith(DROP_PREFIX) && name.endsWith(".mcpack") && name !== pending?.name) {
      try {
        await dropDir.removeEntry(name);
        n++;
      } catch (_) {}
    }
  }
  return n;
}

async function cleanup(auto = false) {
  if (!pending || !dropDir) return;
  const name = pending.name;
  try {
    await dropDir.removeEntry(name);
  } catch (err) {
    if (err.name !== "NotFoundError") {
      $("b-cleanup-text").textContent = `Could not delete ${name}: ${err.message}. Delete it from ${DROP_DIR} yourself.`;
      return;
    }
  }
  pending = null;
  $("b-cleanup").hidden = true;
  $("b-cleanup-text").textContent = auto ? "The temporary .mcpack was deleted." : "Done. The temporary .mcpack was deleted.";
}

// Back on the page a while after Minecraft opened: the import is over.
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && pending?.launchedAt && Date.now() - pending.launchedAt > AUTO_CLEANUP_MS) cleanup(true);
});
window.addEventListener("beforeunload", (ev) => {
  if (pending) {
    ev.preventDefault();
    ev.returnValue = "";
  }
});

// ---------- run ----------

const STEPS = ["zip", "download", "verify", "apply", "write"];

function resetRun() {
  if (worker) return;
  $("b-progress").hidden = true;
  $("b-bar").hidden = true;
  $("b-error").hidden = true;
  $("b-done").hidden = true;
  $("b-start").hidden = false;
  $("b-start").textContent = "Patch";
  for (const li of $("b-progress").children) {
    li.className = "";
    li.querySelector(".wp-progress__val").textContent = "";
  }
}

function markStep(step) {
  const idx = STEPS.indexOf(step);
  for (const li of $("b-progress").children) {
    const i = STEPS.indexOf(li.dataset.step);
    li.className = i < idx ? "is-done" : i === idx ? "is-active" : "";
    if (i < idx) li.querySelector(".wp-progress__val").textContent = "✓";
  }
  setBar(0);
}
const setBar = (f) => ($("b-bar").firstElementChild.style.width = `${Math.round(Math.min(1, Math.max(0, f)) * 100)}%`);

function randomName() {
  const b = new Uint8Array(6);
  crypto.getRandomValues(b);
  return DROP_PREFIX + Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("") + ".mcpack";
}

$("b-start").addEventListener("click", async () => {
  if (!pack || !chosen || !dropDir || worker) return;
  if (pending) await cleanup();
  resetRun();
  $("b-start").hidden = true;
  $("b-folder").disabled = true;
  $("b-progress").hidden = false;
  $("b-bar").hidden = false;

  const enc = chosen.patches.encrypted;
  const folder = chosen.folder_name.split("/").map(encodeURIComponent).join("/");
  const patch = { url: `${LIBRARY}/Patches/${folder}/encrypted.vcdiff`, sha256: enc.sha256, size: enc.size };

  worker = new Worker(new URL("worker.js?v=20261116", import.meta.url), { type: "module" });
  worker.onmessage = async (ev) => {
    const m = ev.data;
    if (m.type === "step") markStep(m.step);
    else if (m.type === "progress") {
      setBar(m.total ? m.done / m.total : 0);
      const v = $("b-progress").querySelector(`[data-step="${m.step}"] .wp-progress__val`);
      if (v) v.textContent = m.step === "zip" || m.step === "download" ? `${mb(m.done)} / ${mb(m.total)}` : `${Math.round((m.done / m.total) * 100)}%`;
    } else if (m.type === "done") {
      const finished = worker;
      try {
        markStep("write");
        const name = randomName();
        const fh = await dropDir.getFileHandle(name, { create: true });
        const w = await fh.createWritable();
        await w.write(m.result);
        await w.close();
        pending = { name, launchedAt: 0 };
        for (const li of $("b-progress").children) {
          li.className = "is-done";
          li.querySelector(".wp-progress__val").textContent = "✓";
        }
        setBar(1);
        $("b-done").hidden = false;
        $("b-import").hidden = false;
        $("b-cleanup").hidden = true;
        $("b-cleanup-text").textContent = "";
        $("b-done-text").innerHTML = `<strong>Patched.</strong> Now let Minecraft import it (${mb(m.result.size)}).`;
      } catch (err) {
        worker = null; // keep fail() from killing it before finally runs
        fail(`Could not write the .mcpack into ${DROP_DIR}: ${err.message}`);
      } finally {
        // Only now: the result Blob came from the worker.
        if (finished) finished.terminate();
        if (worker === finished) worker = null;
        $("b-folder").disabled = false;
        updateStart();
      }
    } else if (m.type === "error") fail(m.message);
  };
  worker.onerror = (e) => fail(e.message || "The patch worker crashed (out of memory?)");
  worker.postMessage({ files: pack.files, patch });
});

// The protocol launch needs a fresh click, so it is its own button.
$("b-import").addEventListener("click", () => {
  if (!pending) return;
  pending.launchedAt = Date.now();
  location.href = `minecraft://?importpack=${DROP_DIR}\\${pending.name}`;
  $("b-import").hidden = true;
  $("b-cleanup").hidden = false;
  $("b-cleanup-text").textContent =
    "Minecraft opens and shows \"Import started\" / \"Successfully imported\". Then come back and click the button: it deletes the temporary file. (It is deleted by itself if you come back after a minute.)";
});
$("b-cleanup").addEventListener("click", () => cleanup());

function fail(message) {
  if (worker) {
    worker.terminate();
    worker = null;
  }
  const el = $("b-error");
  el.hidden = false;
  el.innerHTML =
    `<span><strong>Patching failed:</strong> ${esc(message)}<br>` +
    `Make sure Minecraft has fully downloaded A&amp;S and the pack is unmodified, then try again. ` +
    `Still stuck? Ask in the <a href="https://discord.gg/55nhtqdmYD" rel="noopener">Discord</a>.</span>`;
  const active = $("b-progress").querySelector(".is-active");
  if (active) active.className = "is-failed";
  $("b-start").hidden = false;
  $("b-start").textContent = "Try again";
  $("b-folder").disabled = false;
  updateStart();
}

// ---------- copy buttons ----------

for (const btn of document.querySelectorAll("#steps-browser [data-copy]")) {
  btn.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText($(btn.dataset.copy).textContent);
      btn.textContent = "Copied";
      setTimeout(() => (btn.textContent = "Copy"), 1500);
    } catch (_) {}
  });
}

if (unlocked) loadIndex().catch(() => {});
