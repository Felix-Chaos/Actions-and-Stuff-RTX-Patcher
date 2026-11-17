// Reading the Minecraft folder and installing the patched pack into it, via
// the File System Access API (Chrome / Edge; Firefox has no writable folders).
//
// Mirrors the desktop patcher: the pack comes from premium_cache/resource_packs,
// the result is extracted into resource_packs/<folder> of every games/com.mojang
// the picked folder holds (install_archive_to_targets), an old folder of that
// name is removed first so the result is never a mix.

const SOURCE_PATH = ["premium_cache", "resource_packs"];
// GDK keeps both; the game reads Users/Shared. UWP (LocalState) only has the first.
const TARGET_PATHS = [
  ["games", "com.mojang"],
  ["Users", "Shared", "games", "com.mojang"],
];

async function subdir(dir, names, create = false) {
  let d = dir;
  for (const n of names) d = await d.getDirectoryHandle(n, { create });
  return d;
}

async function trySubdir(dir, names) {
  try {
    return await subdir(dir, names);
  } catch (_) {
    return null;
  }
}

/**
 * Finds where to read from and write to in the picked folder.
 * @returns {Promise<{source: FileSystemDirectoryHandle, targets: {handle: FileSystemDirectoryHandle, label: string}[]}>}
 */
export async function locateMinecraft(root) {
  const source = await trySubdir(root, SOURCE_PATH);
  if (!source) {
    const hint = ["resource_packs", "premium_cache", "com.mojang", "games", "Users"].includes(root.name)
      ? ` You picked "${root.name}": go up to the "Minecraft Bedrock" folder itself.`
      : "";
    throw new Error(`This is not the Minecraft folder (no premium_cache\\resource_packs inside).${hint}`);
  }
  const targets = [];
  for (const path of TARGET_PATHS) {
    const mojang = await trySubdir(root, path);
    if (!mojang) continue;
    targets.push({ handle: await mojang.getDirectoryHandle("resource_packs", { create: true }), label: [...path, "resource_packs"].join("\\") });
  }
  if (targets.length === 0) throw new Error("No games\\com.mojang folder found. Start Minecraft once, close it, and try again.");
  return { source, targets };
}

/** Every file below dir as {segs, file}, segs relative to dir. */
export async function listFiles(dir, prefix = []) {
  const out = [];
  for await (const [name, handle] of dir.entries()) {
    if (handle.kind === "directory") out.push(...(await listFiles(handle, [...prefix, name])));
    else out.push({ segs: [...prefix, name], file: await handle.getFile() });
  }
  return out;
}

/**
 * Entries of a stored (uncompressed) zip, as written by pack_folder_impl and
 * produced by the patch: [{name, start, size}] into bytes.
 */
export function readStoredZip(bytes) {
  const dv = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let eocd = -1;
  for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 22 - 0xffff); i--) {
    if (dv.getUint32(i, true) === 0x06054b50) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) throw new Error("The patched pack is not a valid zip");
  const count = dv.getUint16(eocd + 10, true);
  let p = dv.getUint32(eocd + 16, true);
  const dec = new TextDecoder();
  const entries = [];
  for (let n = 0; n < count; n++) {
    if (dv.getUint32(p, true) !== 0x02014b50) throw new Error("The patched pack has a broken zip directory");
    const method = dv.getUint16(p + 10, true);
    const size = dv.getUint32(p + 20, true);
    const nameLen = dv.getUint16(p + 28, true);
    const extraLen = dv.getUint16(p + 30, true);
    const commentLen = dv.getUint16(p + 32, true);
    const local = dv.getUint32(p + 42, true);
    const name = dec.decode(bytes.subarray(p + 46, p + 46 + nameLen));
    if (method !== 0) throw new Error(`Unexpected compressed entry in the patched pack: ${name}`);
    if (dv.getUint32(local, true) !== 0x04034b50) throw new Error(`Broken zip entry: ${name}`);
    const start = local + 30 + dv.getUint16(local + 26, true) + dv.getUint16(local + 28, true);
    entries.push({ name, start, size });
    p += 46 + nameLen + extraLen + commentLen;
  }
  return entries;
}

function safeSegments(name) {
  const segs = name.split("/").filter((s) => s !== "");
  if (segs.some((s) => s === "." || s === ".." || /[\\:*?"<>|]/.test(s))) throw new Error(`Unsafe path in the patched pack: ${name}`);
  return segs;
}

function explain(err, label) {
  const why = err && err.name === "NoModificationAllowedError"
    ? "a file is in use or write-protected (close Minecraft; if the desktop patcher locked the pack, unlock it there first)"
    : err && err.name === "NotAllowedError"
      ? "the browser has no permission to write there (pick the folder again and allow editing)"
      : (err && err.message) || String(err);
  return new Error(`Could not write to ${label}: ${why}`);
}

/**
 * Extracts the zip into <target>/<folderName> for every target, replacing an
 * existing folder of that name. Returns the labels of the written folders.
 */
export async function installZip(zipBlob, targets, folderName, onProgress = () => {}) {
  const bytes = new Uint8Array(await zipBlob.arrayBuffer());
  const entries = readStoredZip(bytes).filter((e) => !e.name.endsWith("/"));
  const total = entries.length * targets.length;
  let done = 0;
  const written = [];

  for (const t of targets) {
    const label = `${t.label}\\${folderName}`;
    try {
      await t.handle.removeEntry(folderName, { recursive: true });
    } catch (err) {
      if (err.name !== "NotFoundError") throw explain(err, label);
    }
    let dest;
    try {
      dest = await t.handle.getDirectoryHandle(folderName, { create: true });
    } catch (err) {
      throw explain(err, label);
    }

    const dirs = new Map([["", dest]]);
    const dirFor = async (segs) => {
      let key = "";
      let d = dest;
      for (const s of segs) {
        key = key ? `${key}/${s}` : s;
        let next = dirs.get(key);
        if (!next) {
          next = await d.getDirectoryHandle(s, { create: true });
          dirs.set(key, next);
        }
        d = next;
      }
      return d;
    };

    // A few writes at a time: each file is its own small write + rename.
    let i = 0;
    const worker = async () => {
      while (i < entries.length) {
        const e = entries[i++];
        const segs = safeSegments(e.name);
        const dir = await dirFor(segs.slice(0, -1));
        const fh = await dir.getFileHandle(segs[segs.length - 1], { create: true });
        const w = await fh.createWritable();
        await w.write(bytes.subarray(e.start, e.start + e.size));
        await w.close();
        onProgress(++done, total);
      }
    };
    try {
      await Promise.all(Array.from({ length: 8 }, worker));
    } catch (err) {
      throw explain(err, label);
    }
    written.push(label);
  }
  return written;
}
