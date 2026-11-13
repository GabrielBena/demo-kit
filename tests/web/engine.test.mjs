// @ts-check
// The pixel engine's primitives, and the scene rule as a host applies it.

import { test } from "node:test";
import assert from "node:assert/strict";
import { ramp, screen, textWidth, tone } from "../../src/demokit/web/screen.js";
import { glyph } from "../../src/demokit/web/font.js";
import { LOOKS } from "../../src/demokit/web/looks.js";
import { png } from "../../src/demokit/web/png.js";
import { draw } from "../../src/demokit/web/render.mjs";

test("a pixel off the screen is dropped", () => {
  const scr = screen(4, 3);
  scr.rect(-2, -2, 9, 9, 1);
  assert.deepEqual([...scr.px], Array(12).fill(1));
});

test("a tone covers its share of each 4 × 4 block", () => {
  // Bayer's thresholds are (b + 0.5) / 16 for b = 0..15: a share of 0.5 passes 8 of them.
  const scr = screen(4, 4);
  scr.rect(0, 0, 4, 4, tone(1, 0, 0.5));
  assert.equal(scr.px.reduce((a, b) => a + b, 0), 8);
});

test("a ramp without a matrix takes the nearest stop", () => {
  assert.equal(ramp([1, 2, 3], 0.74, null), 2); // 0.74 of the way is 1.48 stops in: the second
  assert.equal(ramp([1, 2, 3], 2, null), 3); // clamped to the last
});

test("text advances six pixels a glyph; an unknown glyph is a box", () => {
  assert.equal(textWidth("AB"), 11);
  assert.deepEqual(glyph("☃"), [0x7f, 0x41, 0x41, 0x41, 0x7f]);
});

test("a PNG has the signature and the scaled size", () => {
  const bytes = png(screen(5, 2), LOOKS.arcade.palette, 3);
  assert.deepEqual([...bytes.subarray(1, 4)], [80, 78, 71]); // "PNG"
  assert.deepEqual([bytes.readUInt32BE(16), bytes.readUInt32BE(20)], [15, 6]);
});

test("a host passes its input to the scene, step, tick and pick defaulted", () => {
  /** @type {any[]} */ const seen = [];
  draw((_scr, _look, data, input) => seen.push(data, input), "data", { tick: 7 }, { w: 8, h: 8 });
  assert.deepEqual(seen, ["data", { step: 0, tick: 7, pick: null }]);
});

test("every look gives every role a colour of its palette", () => {
  for (const [name, L] of Object.entries(LOOKS)) {
    const scr = screen(16, 4);
    for (let i = 0; i < 16; i++) {
      const t = i / 15, v = 2 * t - 1;
      [L.mag(t), L.sign(v), L.level(t), L.value(v)].forEach((c, j) => scr.put(i, j, c));
    }
    assert.ok(scr.px.every((p) => p < L.palette.length), name);
  }
});
