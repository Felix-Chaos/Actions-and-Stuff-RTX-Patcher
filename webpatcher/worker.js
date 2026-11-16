// Runs the patch off the main thread: zip the pack, fetch + verify the patch,
// apply it. Everything stays in this browser tab; nothing is uploaded.

import { buildStoredZip } from "./lib/zipstore.js?v=20261116";
import { applyPatch } from "./lib/vcdiff.js?v=20261116";

const post = (type, data = {}) => self.postMessage({ type, ...data });

async function sha256Hex(bytes) {
  const d = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return Array.from(d, (b) => b.toString(16).padStart(2, "0")).join("");
}

async function download(url, expectedSize) {
  const res = await fetch(url, { cache: "no-cache" });
  if (!res.ok) throw new Error(`Patch download failed (HTTP ${res.status})`);
  const total = Number(res.headers.get("content-length")) || expectedSize || 0;
  if (!res.body) {
    const buf = new Uint8Array(await res.arrayBuffer());
    post("progress", { step: "download", done: buf.length, total: buf.length });
    return buf;
  }
  const reader = res.body.getReader();
  const chunks = [];
  let got = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    got += value.length;
    post("progress", { step: "download", done: got, total: Math.max(total, got) });
  }
  const out = new Uint8Array(got);
  let o = 0;
  for (const c of chunks) {
    out.set(c, o);
    o += c.length;
  }
  return out;
}

self.onmessage = async (ev) => {
  const { files, patch } = ev.data;
  try {
    post("step", { step: "zip" });
    const source = await buildStoredZip(files, (done, total) => post("progress", { step: "zip", done, total }));

    post("step", { step: "download" });
    const patchBytes = await download(patch.url, patch.size);

    post("step", { step: "verify" });
    if (patch.size && patchBytes.length !== patch.size) {
      throw new Error(`Patch download is incomplete (${patchBytes.length} of ${patch.size} bytes)`);
    }
    if (patch.sha256) {
      const got = await sha256Hex(patchBytes);
      if (got !== patch.sha256.toLowerCase()) throw new Error("Patch download is corrupted (SHA-256 mismatch)");
    }

    post("step", { step: "apply" });
    const outputs = await applyPatch(
      patchBytes,
      async (offset, length) => new Uint8Array(await source.slice(offset, offset + length).arrayBuffer()),
      { onProgress: (pos, len) => post("progress", { step: "apply", done: pos, total: len }) }
    );

    const result = new Blob(outputs, { type: "application/zip" });
    post("done", { result });
  } catch (err) {
    post("error", { message: err && err.message ? err.message : String(err) });
  }
};
