// VCDIFF (RFC 3284) decoder with the xdelta3 extensions the RTX patches use:
// LZMA secondary compression of the data/inst/addr sections, an application
// header and a per-window Adler-32 of the target.
//
// Equivalent of `xdelta3 -d -s <source> <patch> <output>`.

import { Lzma2Decoder } from "./lzma2.js?v=20261116";

const VCD_SECONDARY = 0x01;
const VCD_CODETABLE = 0x02;
const VCD_APPHEADER = 0x04;

const VCD_SOURCE = 0x01;
const VCD_TARGET = 0x02;
const VCD_ADLER32 = 0x04;

const VCD_DATACOMP = 0x01;
const VCD_INSTCOMP = 0x02;
const VCD_ADDRCOMP = 0x04;

const LZMA_ID = 2;

const NOOP = 0;
const ADD = 1;
const RUN = 2;
const COPY = 3;

const S_NEAR = 4;
const S_SAME = 3;

// RFC 3284 section 5.6 default code table: [type1, size1, mode1, type2, size2, mode2]
const CODE_TABLE = (() => {
  const t = [];
  t.push([RUN, 0, 0, NOOP, 0, 0]);
  for (let s = 0; s <= 17; s++) t.push([ADD, s, 0, NOOP, 0, 0]);
  for (let m = 0; m <= 8; m++) {
    t.push([COPY, 0, m, NOOP, 0, 0]);
    for (let s = 4; s <= 18; s++) t.push([COPY, s, m, NOOP, 0, 0]);
  }
  for (let m = 0; m <= 5; m++)
    for (let a = 1; a <= 4; a++)
      for (let c = 4; c <= 6; c++) t.push([ADD, a, 0, COPY, c, m]);
  for (let m = 6; m <= 8; m++) for (let a = 1; a <= 4; a++) t.push([ADD, a, 0, COPY, 4, m]);
  for (let m = 0; m <= 8; m++) t.push([COPY, 4, m, ADD, 1, 0]);
  if (t.length !== 256) throw new Error("code table size");
  return t;
})();

function adler32(bytes) {
  let a = 1;
  let b = 0;
  const n = bytes.length;
  let i = 0;
  while (i < n) {
    const end = Math.min(i + 3800, n);
    for (; i < end; i++) {
      a += bytes[i];
      b += a;
    }
    a %= 65521;
    b %= 65521;
  }
  return ((b << 16) | a) >>> 0;
}

class Reader {
  constructor(buf, pos = 0, end = buf.length) {
    this.buf = buf;
    this.pos = pos;
    this.end = end;
  }
  byte() {
    if (this.pos >= this.end) throw new Error("VCDIFF: unexpected end of data");
    return this.buf[this.pos++];
  }
  size() {
    let v = 0;
    for (let i = 0; i < 10; i++) {
      const b = this.byte();
      v = v * 128 + (b & 0x7f);
      if (!(b & 0x80)) return v;
    }
    throw new Error("VCDIFF: integer too long");
  }
  bytes(n) {
    if (this.pos + n > this.end) throw new Error("VCDIFF: section overruns the patch");
    const out = this.buf.subarray(this.pos, this.pos + n);
    this.pos += n;
    return out;
  }
  get done() {
    return this.pos >= this.end;
  }
}

/**
 * Reads [offset, offset+length) of the source, e.g. from a Blob.
 * @callback SourceReader
 * @param {number} offset
 * @param {number} length
 * @returns {Promise<Uint8Array>}
 */

/**
 * Apply an xdelta3 patch.
 * @param {Uint8Array} patch
 * @param {SourceReader} readSource
 * @param {{onProgress?: (patchPos: number, patchLen: number, outLen: number) => void}} [opts]
 * @returns {Promise<Uint8Array[]>} target as a list of window outputs (wrap in a Blob)
 */
export async function applyPatch(patch, readSource, opts = {}) {
  const r = new Reader(patch);
  if (r.byte() !== 0xd6 || r.byte() !== 0xc3 || r.byte() !== 0xc4) throw new Error("Not a VCDIFF patch");
  if (r.byte() !== 0) throw new Error("Unsupported VCDIFF version");

  const hdr = r.byte();
  let secondaryId = 0;
  if (hdr & VCD_SECONDARY) {
    secondaryId = r.byte();
    if (secondaryId !== LZMA_ID) throw new Error(`Unsupported secondary compressor ${secondaryId}`);
  }
  if (hdr & VCD_CODETABLE) throw new Error("Custom code tables are not supported");
  if (hdr & VCD_APPHEADER) r.bytes(r.size());

  // One decoder per section, alive for the whole patch (see lzma2.js).
  const sec = { data: null, inst: null, addr: null };
  const unpack = (key, bytes) => {
    const s = new Reader(bytes);
    const size = s.size();
    if (!sec[key]) sec[key] = new Lzma2Decoder();
    return sec[key].decode(bytes.subarray(s.pos), size);
  };

  const outputs = [];
  let outLen = 0;
  let srcCache = { off: -1, buf: null };

  while (!r.done) {
    const winInd = r.byte();
    if (winInd & VCD_TARGET) throw new Error("VCD_TARGET windows are not supported");
    let srcLen = 0;
    let srcOff = 0;
    if (winInd & VCD_SOURCE) {
      srcLen = r.size();
      srcOff = r.size();
    }
    r.size(); // length of the delta encoding
    const tgtLen = r.size();
    const delInd = r.byte();
    const dataLen = r.size();
    const instLen = r.size();
    const addrLen = r.size();
    let cksum = null;
    if (winInd & VCD_ADLER32) {
      cksum = ((r.byte() << 24) | (r.byte() << 16) | (r.byte() << 8) | r.byte()) >>> 0;
    }
    let data = r.bytes(dataLen);
    let inst = r.bytes(instLen);
    let addr = r.bytes(addrLen);
    if (delInd & VCD_DATACOMP) data = unpack("data", data);
    if (delInd & VCD_INSTCOMP) inst = unpack("inst", inst);
    if (delInd & VCD_ADDRCOMP) addr = unpack("addr", addr);

    let src = null;
    if (srcLen > 0) {
      const c = srcCache;
      if (c.buf && srcOff >= c.off && srcOff + srcLen <= c.off + c.buf.length) {
        src = c.buf.subarray(srcOff - c.off, srcOff - c.off + srcLen);
      } else {
        src = await readSource(srcOff, srcLen);
        if (src.length !== srcLen) throw new Error("Source file is too short for this patch");
        srcCache = { off: srcOff, buf: src };
      }
    }

    const out = new Uint8Array(tgtLen);
    decodeWindow(src, srcLen, out, new Reader(data), new Reader(inst), new Reader(addr));

    if (cksum !== null && !opts.skipChecksum && adler32(out) !== cksum) {
      throw new Error("Checksum mismatch: the selected pack does not match this patch");
    }
    outputs.push(out);
    outLen += tgtLen;
    if (opts.onProgress) opts.onProgress(r.pos, patch.length, outLen);
  }
  return outputs;
}

function decodeWindow(src, srcLen, out, data, inst, addr) {
  const near = new Array(S_NEAR).fill(0);
  let nextSlot = 0;
  const same = new Array(S_SAME * 256).fill(0);
  let pos = 0; // in out

  const decodeAddr = (mode) => {
    const here = srcLen + pos;
    let a;
    if (mode === 0) a = addr.size();
    else if (mode === 1) a = here - addr.size();
    else if (mode - 2 < S_NEAR) a = near[mode - 2] + addr.size();
    else a = same[(mode - 2 - S_NEAR) * 256 + addr.byte()];
    if (S_NEAR > 0) {
      near[nextSlot] = a;
      nextSlot = (nextSlot + 1) % S_NEAR;
    }
    same[a % (S_SAME * 256)] = a;
    if (a >= here) throw new Error("VCDIFF: copy address out of range");
    return a;
  };

  const exec = (type, size, mode) => {
    if (type === NOOP) return;
    if (size === 0) size = inst.size();
    if (pos + size > out.length) throw new Error("VCDIFF: instruction overruns the window");
    if (type === ADD) {
      out.set(data.bytes(size), pos);
      pos += size;
    } else if (type === RUN) {
      out.fill(data.byte(), pos, pos + size);
      pos += size;
    } else {
      const a = decodeAddr(mode);
      if (a + size <= srcLen) {
        out.set(src.subarray(a, a + size), pos);
        pos += size;
      } else if (a >= srcLen) {
        // From the target window itself; may overlap the bytes being written.
        let t = a - srcLen;
        if (t + size <= pos) {
          out.copyWithin(pos, t, t + size);
          pos += size;
        } else {
          for (let i = 0; i < size; i++) out[pos++] = out[t++];
        }
      } else {
        for (let i = 0; i < size; i++, pos++) {
          const s = a + i;
          out[pos] = s < srcLen ? src[s] : out[s - srcLen];
        }
      }
    }
  };

  while (!inst.done) {
    const e = CODE_TABLE[inst.byte()];
    exec(e[0], e[1], e[2]);
    exec(e[3], e[4], e[5]);
  }
  if (pos !== out.length) throw new Error("VCDIFF: window decoded to the wrong size");
}
