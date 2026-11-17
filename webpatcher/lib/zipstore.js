// Deterministic "stored" ZIP builder.
//
// Byte-for-byte identical to pack_folder_impl in the desktop patcher
// (src-tauri/src/utils.rs, zip crate 4.6.1, CompressionMethod::Stored,
// fixed 1980-01-01 timestamp, entries sorted by path). The RTX patches are
// xdelta diffs against exactly that archive, so a single differing byte
// makes every patch fail its checksum.
//
// The archive is returned as a Blob that references the input files instead
// of copying them, so building it costs one read per file (for the CRC).

const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

export function crc32(bytes, crc = 0) {
  let c = ~crc >>> 0;
  for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
  return ~c >>> 0;
}

const utf8 = new TextEncoder();

// Rust's String ordering: plain byte order of the UTF-8 encoding.
function compareBytes(a, b) {
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) if (a[i] !== b[i]) return a[i] - b[i];
  return a.length - b.length;
}

const DOS_TIME = 0x0000; // 00:00:00
const DOS_DATE = 0x0021; // 1980-01-01

/**
 * @param {{path: string, file: Blob}[]} entries  paths relative to the pack root, "/" separated
 * @param {(done: number, total: number) => void} [onProgress]  bytes read so far
 * @returns {Promise<Blob>}
 */
export async function buildStoredZip(entries, onProgress) {
  const items = entries.map((e) => ({ ...e, name: utf8.encode(e.path) }));
  items.sort((a, b) => compareBytes(a.name, b.name));

  const total = items.reduce((s, e) => s + e.file.size, 0);
  let done = 0;
  const parts = [];
  const central = [];
  let offset = 0;

  for (const it of items) {
    const size = it.file.size;
    if (size >= 0xffffffff || offset >= 0xffffffff) {
      throw new Error("Pack too large for a non-ZIP64 archive");
    }
    const crc = crc32(new Uint8Array(await it.file.arrayBuffer()));
    done += size;
    if (onProgress) onProgress(done, total);

    // The zip crate flags names as UTF-8 only when they are not plain ASCII.
    const flags = it.name.some((b) => b > 0x7f) ? 0x0800 : 0;

    const lfh = new DataView(new ArrayBuffer(30 + it.name.length));
    lfh.setUint32(0, 0x04034b50, true);
    lfh.setUint16(4, 10, true); // version needed: 1.0
    lfh.setUint16(6, flags, true);
    lfh.setUint16(8, 0, true); // stored
    lfh.setUint16(10, DOS_TIME, true);
    lfh.setUint16(12, DOS_DATE, true);
    lfh.setUint32(14, crc, true);
    lfh.setUint32(18, size, true);
    lfh.setUint32(22, size, true);
    lfh.setUint16(26, it.name.length, true);
    lfh.setUint16(28, 0, true);
    new Uint8Array(lfh.buffer).set(it.name, 30);

    parts.push(lfh.buffer, it.file);

    const cdh = new DataView(new ArrayBuffer(46 + it.name.length));
    cdh.setUint32(0, 0x02014b50, true);
    cdh.setUint16(4, 0x030a, true); // made by: Unix, 1.0
    cdh.setUint16(6, 10, true);
    cdh.setUint16(8, flags, true);
    cdh.setUint16(10, 0, true);
    cdh.setUint16(12, DOS_TIME, true);
    cdh.setUint16(14, DOS_DATE, true);
    cdh.setUint32(16, crc, true);
    cdh.setUint32(20, size, true);
    cdh.setUint32(24, size, true);
    cdh.setUint16(28, it.name.length, true);
    cdh.setUint16(30, 0, true); // extra
    cdh.setUint16(32, 0, true); // comment
    cdh.setUint16(34, 0, true); // disk
    cdh.setUint16(36, 0, true); // internal attrs
    cdh.setUint32(38, 0o100644 * 0x10000, true); // external attrs: -rw-r--r--
    cdh.setUint32(42, offset, true);
    new Uint8Array(cdh.buffer).set(it.name, 46);
    central.push(cdh.buffer);

    offset += 30 + it.name.length + size;
  }

  if (items.length > 0xffff) throw new Error("Too many files for a non-ZIP64 archive");
  const cdSize = central.reduce((s, b) => s + b.byteLength, 0);
  const eocd = new DataView(new ArrayBuffer(22));
  eocd.setUint32(0, 0x06054b50, true);
  eocd.setUint16(8, items.length, true);
  eocd.setUint16(10, items.length, true);
  eocd.setUint32(12, cdSize, true);
  eocd.setUint32(16, offset, true);

  return new Blob([...parts, ...central, eocd.buffer], { type: "application/zip" });
}
