// @ts-check
// A screen as a PNG, scaled by a whole number (node only: for mockups and golden tests).

import { deflateSync } from "node:zlib";

const CRC = Int32Array.from({ length: 256 }, (_, n) => {
  for (let k = 0; k < 8; k++) n = n & 1 ? 0xedb88320 ^ (n >>> 1) : n >>> 1;
  return n;
});
const crc = (/** @type {Buffer} */ b) => (b.reduce((c, x) => CRC[(c ^ x) & 255] ^ (c >>> 8), -1) ^ -1) >>> 0;

function chunk(/** @type {string} */ type, /** @type {Buffer} */ data) {
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const out = Buffer.alloc(body.length + 8);
  out.writeUInt32BE(data.length, 0);
  body.copy(out, 4);
  out.writeUInt32BE(crc(body), body.length + 4);
  return out;
}

/** @param {{w: number, h: number, px: Uint8Array}} scr  @param {string[]} palette  "#rrggbb" */
export function png(scr, palette, scale = 1) {
  const rgb = palette.map((c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16)));
  const W = scr.w * scale, H = scr.h * scale, row = 1 + 3 * W;
  const raw = Buffer.alloc(row * H);
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      const [r, g, b] = rgb[scr.px[Math.floor(y / scale) * scr.w + Math.floor(x / scale)]];
      raw.set([r, g, b], y * row + 1 + 3 * x);
    }
  const head = Buffer.alloc(13);
  head.writeUInt32BE(W, 0);
  head.writeUInt32BE(H, 4);
  head.set([8, 2, 0, 0, 0], 8); // 8 bits, RGB
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  return Buffer.concat([sig, chunk("IHDR", head), chunk("IDAT", deflateSync(raw)), chunk("IEND", Buffer.alloc(0))]);
}
