// Streaming .xz / LZMA2 decoder for xdelta3's LZMA secondary compression.
//
// xdelta3 keeps ONE xz stream per section (data, instructions, addresses)
// for the whole patch and ends every window with LZMA_SYNC_FLUSH. Each
// window therefore carries a run of complete LZMA2 chunks that continue the
// previous window's dictionary and coder state, and the stream is never
// finished. Off-the-shelf xz decoders expect whole streams, hence this one:
// feed it each window's bytes, ask for exactly the decoded size.
//
// Based on the LZMA SDK / xz-embedded reference decoders (public domain).

const XZ_MAGIC = [0xfd, 0x37, 0x7a, 0x58, 0x5a, 0x00];

const kNumStates = 12;
const kMatchMinLen = 2;
const kEndPosModelIndex = 14;
const kNumFullDistances = 128;
const kNumAlignBits = 4;

class LenDecoder {
  constructor() {
    this.choice = new Uint16Array(2);
    this.low = new Uint16Array(16 << 3);
    this.mid = new Uint16Array(16 << 3);
    this.high = new Uint16Array(256);
  }
  reset() {
    this.choice.fill(1024);
    this.low.fill(1024);
    this.mid.fill(1024);
    this.high.fill(1024);
  }
}

export class Lzma2Decoder {
  constructor() {
    this.headerDone = false;
    this.dict = null;
    this.dictSize = 0;
    this.dictPos = 0; // write position in the circular buffer
    this.dictFull = 0; // bytes of history available (<= dictSize)
    this.totalPos = 0; // bytes since the last dictionary reset (posState / literal context)
    this.needDictReset = true;
    this.needProps = true;

    this.lc = 0;
    this.lp = 0;
    this.pb = 0;

    this.isMatch = new Uint16Array(kNumStates << 4);
    this.isRep = new Uint16Array(kNumStates);
    this.isRepG0 = new Uint16Array(kNumStates);
    this.isRepG1 = new Uint16Array(kNumStates);
    this.isRepG2 = new Uint16Array(kNumStates);
    this.isRep0Long = new Uint16Array(kNumStates << 4);
    this.posSlot = new Uint16Array(4 << 6);
    this.specPos = new Uint16Array(kNumFullDistances - kEndPosModelIndex + 1);
    this.align = new Uint16Array(1 << kNumAlignBits);
    this.lenDec = new LenDecoder();
    this.repLenDec = new LenDecoder();
    this.literal = new Uint16Array(0x300 << 4); // lc + lp <= 4

    this.state = 0;
    this.rep0 = 0;
    this.rep1 = 0;
    this.rep2 = 0;
    this.rep3 = 0;

    // range coder
    this.buf = null;
    this.inPos = 0;
    this.range = 0;
    this.code = 0;

    // output of the current call
    this.out = null;
    this.outPos = 0;
  }

  /**
   * Decode the next part of the stream.
   * @param {Uint8Array} input  this window's compressed bytes (after xdelta's size prefix)
   * @param {number} outSize    decoded size xdelta recorded for this window
   * @returns {Uint8Array}
   */
  decode(input, outSize) {
    this.buf = input;
    this.inPos = 0;
    this.out = new Uint8Array(outSize);
    this.outPos = 0;

    if (!this.headerDone) this.readXzHeaders();

    while (this.inPos < input.length) {
      const c = input[this.inPos++];
      if (c === 0x00) throw new Error("LZMA2: unexpected end of stream");

      if (c === 0x01 || c === 0x02) {
        // Uncompressed chunk; 0x01 also resets the dictionary.
        const size = ((input[this.inPos] << 8) | input[this.inPos + 1]) + 1;
        this.inPos += 2;
        if (c === 0x01) this.resetDict();
        else if (this.needDictReset) throw new Error("LZMA2: missing dictionary reset");
        for (let i = 0; i < size; i++) this.putByte(input[this.inPos++]);
        continue;
      }

      if (c < 0x80) throw new Error("LZMA2: invalid chunk control byte " + c);

      const unpacked = ((c & 0x1f) << 16) + ((input[this.inPos] << 8) | input[this.inPos + 1]) + 1;
      const packed = ((input[this.inPos + 2] << 8) | input[this.inPos + 3]) + 1;
      this.inPos += 4;
      const mode = (c >> 5) & 3;
      if (mode === 3) this.resetDict();
      else if (this.needDictReset) throw new Error("LZMA2: missing dictionary reset");
      if (mode >= 2) {
        this.setProps(input[this.inPos++]);
      } else if (this.needProps) {
        throw new Error("LZMA2: missing properties");
      }
      if (mode >= 1) this.resetState();

      const chunkEnd = this.inPos + packed;
      this.initRangeCoder();
      this.decodeLzma(unpacked);
      this.inPos = chunkEnd;
    }

    if (this.outPos !== outSize) {
      throw new Error(`LZMA2: decoded ${this.outPos} bytes, expected ${outSize}`);
    }
    const out = this.out;
    this.out = null;
    this.buf = null;
    return out;
  }

  readXzHeaders() {
    const b = this.buf;
    for (let i = 0; i < 6; i++) if (b[i] !== XZ_MAGIC[i]) throw new Error("xz: bad magic");
    // 2 bytes stream flags + 4 bytes CRC32
    let p = 12;
    const headerSize = (b[p] + 1) * 4;
    const blockStart = p;
    const flags = b[p + 1];
    p += 2;
    if ((flags & 0x03) !== 0) throw new Error("xz: only single-filter blocks are supported");
    if (flags & 0x40) p = this.skipVli(p); // compressed size
    if (flags & 0x80) p = this.skipVli(p); // uncompressed size
    const filterId = b[p++];
    if (filterId !== 0x21) throw new Error("xz: expected the LZMA2 filter");
    p++; // properties size (1)
    const d = b[p] & 0x3f;
    if (d > 40) throw new Error("xz: invalid dictionary size");
    this.dictSize = d === 40 ? 0xffffffff : (2 | (d & 1)) * 2 ** ((d >> 1) + 11);
    // Never need more history than the data we will ever see, but the size
    // stays capped by what the encoder announced.
    this.dictSize = Math.min(this.dictSize, 1 << 30);
    this.dict = new Uint8Array(this.dictSize);
    this.inPos = blockStart + headerSize;
    this.headerDone = true;
  }

  skipVli(p) {
    while (this.buf[p++] & 0x80);
    return p;
  }

  resetDict() {
    this.dictPos = 0;
    this.dictFull = 0;
    this.totalPos = 0;
    this.needDictReset = false;
  }

  setProps(byte) {
    if (byte > 224) throw new Error("LZMA2: invalid properties");
    this.lc = byte % 9;
    byte = (byte / 9) | 0;
    this.lp = byte % 5;
    this.pb = (byte / 5) | 0;
    if (this.lc + this.lp > 4) throw new Error("LZMA2: lc + lp > 4");
    this.needProps = false;
  }

  resetState() {
    this.isMatch.fill(1024);
    this.isRep.fill(1024);
    this.isRepG0.fill(1024);
    this.isRepG1.fill(1024);
    this.isRepG2.fill(1024);
    this.isRep0Long.fill(1024);
    this.posSlot.fill(1024);
    this.specPos.fill(1024);
    this.align.fill(1024);
    this.lenDec.reset();
    this.repLenDec.reset();
    this.literal.fill(1024);
    this.state = 0;
    this.rep0 = this.rep1 = this.rep2 = this.rep3 = 0;
  }

  // ---- output / dictionary ----

  putByte(b) {
    this.dict[this.dictPos++] = b;
    if (this.dictPos === this.dictSize) this.dictPos = 0;
    if (this.dictFull < this.dictSize) this.dictFull++;
    this.totalPos++;
    if (this.outPos >= this.out.length) throw new Error("LZMA2: output overrun");
    this.out[this.outPos++] = b;
  }

  // dist: 0 = the byte just written
  getByte(dist) {
    let i = this.dictPos - dist - 1;
    if (i < 0) i += this.dictSize;
    return this.dict[i];
  }

  // ---- range coder ----

  initRangeCoder() {
    const b = this.buf;
    if (b[this.inPos] !== 0) throw new Error("LZMA: bad range coder init");
    this.code = ((b[this.inPos + 1] << 24) | (b[this.inPos + 2] << 16) | (b[this.inPos + 3] << 8) | b[this.inPos + 4]) >>> 0;
    this.range = 0xffffffff;
    this.inPos += 5;
  }

  bit(probs, i) {
    let p = probs[i];
    const bound = (this.range >>> 11) * p;
    let r;
    if (this.code < bound) {
      this.range = bound;
      probs[i] = p + ((2048 - p) >>> 5);
      r = 0;
    } else {
      this.range = (this.range - bound) >>> 0;
      this.code = (this.code - bound) >>> 0;
      probs[i] = p - (p >>> 5);
      r = 1;
    }
    if (this.range < 0x1000000) {
      this.range = (this.range * 256) >>> 0;
      this.code = ((this.code * 256) + this.buf[this.inPos++]) >>> 0;
    }
    return r;
  }

  directBits(count) {
    let res = 0;
    while (count-- > 0) {
      this.range = this.range >>> 1;
      let b = 0;
      if (this.code >= this.range) {
        this.code = (this.code - this.range) >>> 0;
        b = 1;
      }
      res = res * 2 + b;
      if (this.range < 0x1000000) {
        this.range = (this.range * 256) >>> 0;
        this.code = ((this.code * 256) + this.buf[this.inPos++]) >>> 0;
      }
    }
    return res;
  }

  bitTree(probs, base, numBits) {
    let m = 1;
    for (let i = 0; i < numBits; i++) m = (m << 1) | this.bit(probs, base + m);
    return m - (1 << numBits);
  }

  reverseBitTree(probs, base, numBits) {
    let m = 1;
    let sym = 0;
    for (let i = 0; i < numBits; i++) {
      const b = this.bit(probs, base + m);
      m = (m << 1) | b;
      sym |= b << i;
    }
    return sym;
  }

  decodeLen(ld, posState) {
    if (this.bit(ld.choice, 0) === 0) return this.bitTree(ld.low, posState << 3, 3);
    if (this.bit(ld.choice, 1) === 0) return 8 + this.bitTree(ld.mid, posState << 3, 3);
    return 16 + this.bitTree(ld.high, 0, 8);
  }

  // ---- LZMA ----

  decodeLzma(unpacked) {
    const end = this.outPos + unpacked;
    if (end > this.out.length) throw new Error("LZMA2: chunk exceeds the window's decoded size");
    const pbMask = (1 << this.pb) - 1;
    const lpMask = (1 << this.lp) - 1;
    const lc = this.lc;

    while (this.outPos < end) {
      const posState = this.totalPos & pbMask;
      const st = this.state;

      if (this.bit(this.isMatch, (st << 4) + posState) === 0) {
        // literal
        const prev = this.totalPos > 0 ? this.getByte(0) : 0;
        const base = 0x300 * (((this.totalPos & lpMask) << lc) + (prev >> (8 - lc)));
        let sym = 1;
        if (st >= 7) {
          let matchByte = this.getByte(this.rep0);
          do {
            const matchBit = (matchByte >> 7) & 1;
            matchByte <<= 1;
            const b = this.bit(this.literal, base + 0x100 + (matchBit << 8) + sym);
            sym = (sym << 1) | b;
            if (matchBit !== b) break;
          } while (sym < 0x100);
        }
        while (sym < 0x100) sym = (sym << 1) | this.bit(this.literal, base + sym);
        this.putByte(sym & 0xff);
        this.state = st < 4 ? 0 : st < 10 ? st - 3 : st - 6;
        continue;
      }

      let len;
      if (this.bit(this.isRep, st) === 1) {
        if (this.totalPos === 0) throw new Error("LZMA: rep match at stream start");
        if (this.bit(this.isRepG0, st) === 0) {
          if (this.bit(this.isRep0Long, (st << 4) + posState) === 0) {
            // short rep: one byte at rep0
            this.state = st < 7 ? 9 : 11;
            this.putByte(this.getByte(this.rep0));
            continue;
          }
        } else {
          let dist;
          if (this.bit(this.isRepG1, st) === 0) {
            dist = this.rep1;
          } else {
            if (this.bit(this.isRepG2, st) === 0) {
              dist = this.rep2;
            } else {
              dist = this.rep3;
              this.rep3 = this.rep2;
            }
            this.rep2 = this.rep1;
          }
          this.rep1 = this.rep0;
          this.rep0 = dist;
        }
        len = this.decodeLen(this.repLenDec, posState);
        this.state = st < 7 ? 8 : 11;
      } else {
        this.rep3 = this.rep2;
        this.rep2 = this.rep1;
        this.rep1 = this.rep0;
        len = this.decodeLen(this.lenDec, posState);
        this.state = st < 7 ? 7 : 10;

        const lenState = len < 3 ? len : 3;
        const slot = this.bitTree(this.posSlot, lenState << 6, 6);
        let dist;
        if (slot < 4) {
          dist = slot;
        } else {
          const numDirect = (slot >> 1) - 1;
          dist = (2 | (slot & 1)) * 2 ** numDirect;
          if (slot < kEndPosModelIndex) {
            dist += this.reverseBitTree(this.specPos, dist - slot - 1, numDirect);
          } else {
            dist += this.directBits(numDirect - kNumAlignBits) * 16;
            dist += this.reverseBitTree(this.align, 0, kNumAlignBits);
            if (dist === 0xffffffff) throw new Error("LZMA: unexpected end marker");
          }
        }
        this.rep0 = dist;
      }

      len += kMatchMinLen;
      if (this.rep0 >= this.dictFull) throw new Error("LZMA: match distance beyond history");
      if (this.outPos + len > end) throw new Error("LZMA: match crosses the chunk end");
      const d = this.rep0;
      for (let i = 0; i < len; i++) this.putByte(this.getByte(d));
    }
  }
}
