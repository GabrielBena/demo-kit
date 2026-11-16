// @ts-check
// The live page's pure parts: a chunk off the wire, what a scene sees, what the page keeps.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { chipAt, chips, decode, needed, tape } from "../../src/demokit/web/live.js";

/** @typedef {import("../../src/demokit/web/live.js").Chunk} Chunk */

test("a chunk written by the Python side reads back whole", () => {
  const bytes = readFileSync(new URL("../fixtures/chunk.bin", import.meta.url)); // tests/test_live.py
  const c = decode(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
  assert.deepEqual([c.t0, c.t1, c.key, c.meta], [5, 15, true, { tag: "x" }]);
  assert.deepEqual([...c.arrays.who], [1, 2, 3]);
  assert.deepEqual([...c.arrays.when], [5.5, 7.25, 14]);
  assert.deepEqual([[...c.arrays.grid], c.shapes.grid], [[0, 1, 2, 3, 4, 5], [2, 3]]);
  assert.equal(c.arrays.none.length, 0);
});

/** Chunks of 10 world units from 0, keyframes where `keys` says. */
const run = (/** @type {boolean[]} */ keys) =>
  keys.map((key, i) => /** @type {Chunk} */ ({ t0: 10 * i, t1: 10 * i + 10, key, meta: {}, arrays: {}, shapes: {} }));

test("a scene sees the chunks begun by now, and the last keyframe among them", () => {
  const view = tape(run([true, false, true, false]), 25);
  assert.deepEqual(view.chunks.map((c) => c.t0), [0, 10, 20]);
  assert.equal(view.key?.t0, 20);
});

test("the page keeps from the last keyframe by now, and back a span", () => {
  const chunks = run([true, false, true, false, false]);
  assert.equal(needed(chunks, 45, 0), 2); // the keyframe at 20 holds the state
  assert.equal(needed(chunks, 45, 30), 1); // a span of 30 reaches back into the chunk at 10
  assert.equal(needed(run([false, false, false]), 25, 0), 2); // no keyframe: only what is current
});

test("the device chips sit right-aligned, the CPU first, a taken card not free", () => {
  const cards = [
    { uuid: "GPU-a", index: 0, used: 620, total: 1000, util: 50, free: true },
    { uuid: "GPU-b", index: 1, used: null, total: null, util: null, free: false },
  ];
  const list = chips({ device: "GPU-a", cards }, 320, 180);
  assert.deepEqual(list.map((c) => [c.label, c.state]), [["CPU", "free"], ["G0", "here"], ["G1", "taken"]]);
  const last = list[list.length - 1];
  assert.equal(last.x + last.w, 318);
  assert.deepEqual([list[1].used, list[1].util, list[2].used], [0.62, 0.5, 0]);
  assert.equal(chipAt(list, [list[2].x + 1, 175])?.label, "G1");
  assert.equal(chipAt(list, [10, 175]), null);
});
