// @ts-check
// The screen: an indexed framebuffer, every pixel a palette index, the whole scene drawn again
// each frame from the state (immediate mode: no scene graph, nothing retained). A colour is a
// palette index, or a tone: two indices mixed by ordered dithering, the mix's share `t` decided
// pixel by pixel against a threshold matrix, so a few colours make every shade.

import { glyph, GLYPH_W, GLYPH_H } from "./font.js";

/** @typedef {number | [number, number, number, Float32Array?]} Colour  index, or [a, b, t, matrix] */

const matrix = (/** @type {number[]} */ m) => Float32Array.from(m, (b) => (b + 0.5) / m.length);
export const BAYER = matrix([0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5]); // 4 × 4
export const LINES = matrix([0, 0, 0, 0, 8, 8, 8, 8, 4, 4, 4, 4, 12, 12, 12, 12]); // rows

/** A tone: `a` on a share t of the pixels, `b` on the rest, by `m`'s pattern. */
export const tone = (/** @type {number} */ a, /** @type {number} */ b, /** @type {number} */ t, /** @type {Float32Array} */ m = BAYER) =>
  /** @type {Colour} */ ([a, b, Math.min(Math.max(t, 0), 1), m]);

/** A ramp through palette indices: t in [0, 1] -> a tone between the two stops around it, or,
 *  with no matrix, the nearest stop (flat: for cells that each show one value). */
export function ramp(/** @type {number[]} */ stops, /** @type {number} */ t, /** @type {Float32Array | null} */ m = BAYER) {
  const x = Math.min(Math.max(t, 0), 1) * (stops.length - 1);
  if (m === null) return stops[Math.round(x)];
  const i = Math.min(Math.floor(x), stops.length - 2);
  return tone(stops[i + 1], stops[i], x - i, m);
}

export function screen(/** @type {number} */ w, /** @type {number} */ h) {
  const px = new Uint8Array(w * h);

  /** One pixel; off-screen pixels are dropped. */
  function put(/** @type {number} */ x, /** @type {number} */ y, /** @type {Colour} */ c) {
    if (x < 0 || y < 0 || x >= w || y >= h) return;
    if (typeof c === "number") px[y * w + x] = c;
    else px[y * w + x] = c[2] > (c[3] ?? BAYER)[(y & 3) * 4 + (x & 3)] ? c[0] : c[1];
  }

  return {
    w,
    h,
    px,
    put,
    clear(/** @type {Colour} */ c = 0) {
      this.rect(0, 0, w, h, c);
    },
    /** A filled rectangle. */
    rect(/** @type {number} */ x, /** @type {number} */ y, /** @type {number} */ rw, /** @type {number} */ rh, /** @type {Colour} */ c) {
      for (let j = y; j < y + rh; j++) for (let i = x; i < x + rw; i++) put(i, j, c);
    },
    /** A rectangle's outline, one pixel wide. */
    box(/** @type {number} */ x, /** @type {number} */ y, /** @type {number} */ rw, /** @type {number} */ rh, /** @type {Colour} */ c) {
      this.rect(x, y, rw, 1, c);
      this.rect(x, y + rh - 1, rw, 1, c);
      this.rect(x, y, 1, rh, c);
      this.rect(x + rw - 1, y, 1, rh, c);
    },
    /** A line, by Bresenham's walk. */
    line(/** @type {number} */ x0, /** @type {number} */ y0, /** @type {number} */ x1, /** @type {number} */ y1, /** @type {Colour} */ c) {
      const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0);
      const sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
      for (let e = dx + dy; ; ) {
        put(x0, y0, c);
        if (x0 === x1 && y0 === y1) return;
        const e2 = 2 * e;
        if (e2 >= dy) (e += dy), (x0 += sx);
        if (e2 <= dx) (e += dx), (y0 += sy);
      }
    },
    /** A sprite: rows of characters, each a key of `keys` (a colour) or skipped (transparent). */
    sprite(/** @type {string[]} */ rows, /** @type {number} */ x, /** @type {number} */ y, /** @type {Record<string, Colour>} */ keys) {
      rows.forEach((row, j) => [...row].forEach((ch, i) => ch in keys && put(x + i, y + j, keys[ch])));
    },
    /** A grid of values, one cell each: cell (i, j) of `cw` × `ch` pixels coloured by `colour`. */
    cells(/** @type {ArrayLike<ArrayLike<number>>} */ grid, /** @type {number} */ x, /** @type {number} */ y, /** @type {number} */ cw, /** @type {number} */ ch, /** @type {(v: number, i: number, j: number) => Colour | null} */ colour) {
      for (let j = 0; j < grid.length; j++)
        for (let i = 0; i < grid[j].length; i++) {
          const c = colour(grid[j][i], i, j);
          if (c !== null) this.rect(x + i * cw, y + j * ch, cw, ch, c);
        }
    },
    /** Text in the 5 × 7 font, one pixel apart, each pixel k × k; returns the x after the last glyph. */
    text(/** @type {string} */ s, /** @type {number} */ x, /** @type {number} */ y, /** @type {Colour} */ c, k = 1) {
      for (const ch of s) {
        const cols = glyph(ch);
        for (let i = 0; i < GLYPH_W; i++) for (let j = 0; j < GLYPH_H; j++) if ((cols[i] >> j) & 1) this.rect(x + k * i, y + k * j, k, k, c);
        x += k * (GLYPH_W + 1);
      }
      return x;
    },
  };
}

/** @typedef {ReturnType<typeof screen>} Screen */

/** The width of `s` in the font, in pixels. */
export const textWidth = (/** @type {string} */ s) => [...s].length * (GLYPH_W + 1) - 1;
