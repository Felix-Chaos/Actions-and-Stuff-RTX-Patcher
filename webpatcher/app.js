// Web Patcher UI. The work happens in the A&S RTX Helper (asrtx-helper.exe,
// source: AS-RTX-Patcher-Main/helper): this page starts it through an
// asrtx://start?s=<session> link, then follows it over its local API on
// 127.0.0.1. The helper finds A&S in the Marketplace cache, downloads the
// chosen patch, applies it and extracts the result into resource_packs, so no
// shareable .mcpack is ever created.

const LIBRARY = (() => {
  const real = "https://raw.githubusercontent.com/Felix-Chaos/AS-RTX-Patch-Library/main";
  // Local testing only: ?library=<url> on localhost swaps in a test catalogue
  // (the helper then needs ASRTX_LIBRARY set to the same place).
  const local = ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
  const override = local && new URLSearchParams(location.search).get("library");
  return override ? new URL(override, location.href).href.replace(/\/$/, "") : real;
})();
const HELPER = "http://127.0.0.1:47613";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

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
if (unlocked) loadIndex().catch(() => {});

let session = null;
let pack = null; // chosen candidate from the helper's scan
let entries = [];
let chosen = null;
let busy = false;

// ---------- helper API ----------

async function helper(path, opts = {}) {
  const res = await fetch(`${HELPER}${path}${path.includes("?") ? "&" : "?"}s=${session}`, {
    cache: "no-store",
    targetAddressSpace: "loopback", // Chrome's Local Network Access; ignored elsewhere
    ...opts,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(body.error || `HTTP ${res.status}`);
    err.code = body.error;
    throw err;
  }
  return body;
}

function newSession() {
  const b = new Uint8Array(16);
  crypto.getRandomValues(b);
  return Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
}

// Chromium shows its "Open A&S RTX Helper?" prompt and stays on the page.
// Firefox would replace the page with an error if the helper is not installed,
// so it launches from a hidden iframe instead.
function launch(url) {
  if (!("MozAppearance" in document.documentElement.style)) {
    location.href = url;
    return;
  }
  const f = document.createElement("iframe");
  f.hidden = true;
  f.src = url;
  document.body.appendChild(f);
  setTimeout(() => f.remove(), 5000);
}

// ---------- matching (resolvePatchConfig's "solid hit") ----------

function fits(entry, cand) {
  const valid = entry.validation || {};
  const stats = entry.stats || entry.marketplace_pack_stats?.v1 || {};
  const hashOk = !(valid.logo_hash && cand.logoHash) || valid.logo_hash === cand.logoHash;
  const filesOk = !stats.files || Math.abs(stats.files - cand.files) <= 5;
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

$("find").addEventListener("click", async () => {
  if (busy) return;
  resetRun();
  pack = null;
  chosen = null;
  unlock("step-patch", false);
  $("start").disabled = true;
  $("patch-box").innerHTML = `<p class="wp-hint">Find your pack first.</p>`;

  session = newSession();
  launch(`asrtx://start?s=${session}`);
  setResult("Starting the helper… allow <em>Open A&amp;S RTX Helper</em> if your browser asks.");
  $("find").disabled = true;

  const started = Date.now();
  let status = null;
  let hinted = false;
  while (Date.now() - started < 120000) {
    try {
      status = await helper("/status");
      if (status.state !== "scanning") break;
      setResult("Looking for Actions &amp; Stuff…");
    } catch (err) {
      if (err.code === "busy") {
        setResult("The helper is busy with a patch started in another tab. Wait until it is done, then try again.", "warn");
        $("find").disabled = false;
        return;
      }
      if (!hinted && Date.now() - started > 10000) {
        hinted = true;
        setResult(
          "Still waiting for the helper. Not installed yet? Do step 1 first. " +
            "Chrome/Edge: allow this site to access apps on your device (icon in the address bar).",
          "warn"
        );
      }
    }
    await sleep(700);
  }
  $("find").disabled = false;
  if (!status || status.state === "scanning") {
    setResult("The helper did not answer. Run <code>asrtx-helper.exe</code> once (step 1) and click the button again.", "warn");
    return;
  }

  try {
    entries = await loadIndex();
  } catch (err) {
    indexPromise = null;
    setResult(`Could not load the patch list: ${esc(err.message)}. Check your connection and try again.`, "warn");
    return;
  }

  const candidates = status.packs || [];
  if (candidates.length === 0) {
    setResult("No Actions &amp; Stuff found in the Marketplace cache. Start Minecraft once so it downloads A&amp;S, close it, and try again.", "warn");
    return;
  }
  const rank = (c) => (entries.some((e) => fits(e, c)) ? 2 : entries.some((e) => sameVersion(e, c)) ? 1 : 0);
  candidates.sort((a, b) => rank(b) - rank(a) || b.files - a.files);
  pack = candidates[0];
  setResult(
    `Found <strong>Actions &amp; Stuff ${esc(pack.version || "(unknown version)")}</strong> · ${pack.files} files` +
      ` <span class="wp-muted">(helper ${esc(status.helperVersion)})</span>`,
    "ok"
  );
  renderPatchChoice();
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
  $("start").disabled = false;
}

// ---------- run ----------

const STEPS = ["download", "verify", "zip", "apply", "install"];

function resetRun() {
  $("progress").hidden = true;
  $("bar").hidden = true;
  $("error").hidden = true;
  $("done").hidden = true;
  $("start").hidden = false;
  $("start").disabled = !chosen;
  $("start").textContent = "Patch & install";
  for (const li of $("progress").children) {
    li.className = "";
    li.querySelector(".wp-progress__val").textContent = "";
  }
}

function showProgress(st) {
  const idx = STEPS.indexOf(st.step);
  for (const li of $("progress").children) {
    const i = STEPS.indexOf(li.dataset.step);
    li.className = i < idx ? "is-done" : i === idx ? "is-active" : "";
    const val = li.querySelector(".wp-progress__val");
    if (i < idx) val.textContent = "✓";
    else if (i === idx) {
      val.textContent =
        !st.total ? "…" : st.step === "download" ? `${mb(st.done)} / ${mb(st.total)}` : st.step === "verify" ? "" : `${Math.round((st.done / st.total) * 100)}%`;
    } else val.textContent = "";
  }
  const frac = st.total ? st.done / st.total : 0;
  $("bar").firstElementChild.style.width = `${Math.round(Math.min(1, frac) * 100)}%`;
}

$("start").addEventListener("click", async () => {
  if (!pack || !chosen || busy) return;
  resetRun();
  busy = true;
  $("start").hidden = true;
  $("find").disabled = true;
  $("progress").hidden = false;
  $("bar").hidden = false;

  try {
    await helper(`/patch?pack=${encodeURIComponent(pack.id)}&slug=${encodeURIComponent(chosen.slug)}`, { method: "POST" });
    let misses = 0;
    for (;;) {
      await sleep(500);
      let st;
      try {
        st = await helper("/status");
        misses = 0;
      } catch (err) {
        if (++misses > 20) throw new Error("Lost contact with the helper. Was it closed?");
        continue;
      }
      if (st.state === "running") showProgress(st);
      else if (st.state === "done") {
        for (const li of $("progress").children) {
          li.className = "is-done";
          li.querySelector(".wp-progress__val").textContent = "✓";
        }
        $("bar").firstElementChild.style.width = "100%";
        $("done-text").innerHTML =
          `<strong>Installed.</strong> The pack is now in<br>` + st.installed.map((p) => `<code>${esc(p)}</code>`).join("<br>");
        $("done").hidden = false;
        break;
      } else if (st.state === "error") {
        throw new Error(st.message || "The helper reported an error.");
      }
    }
  } catch (err) {
    fail(err.code === "session" ? "The helper was restarted from another tab. Click Find my Actions & Stuff again." : err.message);
  } finally {
    busy = false;
    $("find").disabled = false;
  }
});

function fail(message) {
  const el = $("error");
  el.hidden = false;
  el.innerHTML =
    `<span><strong>Patching failed:</strong> ${esc(message)}<br>` +
    `Make sure Minecraft is closed and has fully downloaded A&amp;S, then try again. ` +
    `Still stuck? Ask in the <a href="https://discord.gg/55nhtqdmYD" rel="noopener">Discord</a>.</span>`;
  const active = $("progress").querySelector(".is-active");
  if (active) active.className = "is-failed";
  $("start").hidden = false;
  $("start").disabled = false;
  $("start").textContent = "Try again";
}
