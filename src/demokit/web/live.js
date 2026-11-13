// @ts-check
// A live page: the chunks a demokit server streams (demokit/live.py), played at a steady pace of
// world time, a scene drawn at every frame. The page pulls chunks until it holds `ahead` seconds of
// playing; it keeps them from the last keyframe at or before now, and back `span` world units, so a
// scene can draw the state as a whole (the keyframe) and what happened lately (a glow that fades).
// If the loop falls behind, the clock waits for it. Keys: space plays or pauses; ] or → doubles the
// speed, [ or ← halves it. A click reaches the scene as `pick` and the source as a message.

import { screen } from "./screen.js";
import { LOOKS } from "./looks.js";
import { at, blit } from "./blit.js";

/** @typedef {Float32Array | Float64Array | Int8Array | Uint8Array | Int16Array | Uint16Array | Int32Array | Uint32Array} Typed */
/** @typedef {{t0: number, t1: number, key: boolean, meta: Record<string, any>,
 *   arrays: Record<string, Typed>, shapes: Record<string, number[]>}} Chunk */
/** @typedef {{t: number, key: Chunk | null, chunks: Chunk[]}} Tape  what a scene's `data` holds */
/** @typedef {(scr: import("./screen.js").Screen, look: import("./looks.js").Look, data: Tape,
 *   input: {step: number, tick: number, pick: number[] | null, t: number, speed: number, playing: boolean}) => void} Scene */

const TYPES = {
  float32: Float32Array, float64: Float64Array, int8: Int8Array, uint8: Uint8Array,
  int16: Int16Array, uint16: Uint16Array, int32: Int32Array, uint32: Uint32Array,
};

/** A chunk from its bytes (the wire format in demokit/live.py). */
export function decode(/** @type {ArrayBuffer} */ buf) {
  const n = new DataView(buf).getUint32(0, true);
  const head = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, n)));
  const start = (4 + n + 7) & ~7;
  /** @type {Chunk} */
  const c = { t0: head.t0, t1: head.t1, key: head.key, meta: head.meta, arrays: {}, shapes: {} };
  for (const [name, dtype, shape, offset, nbytes] of head.arrays) {
    const T = TYPES[/** @type {keyof typeof TYPES} */ (dtype)];
    c.arrays[name] = new T(buf, start + offset, nbytes / T.BYTES_PER_ELEMENT);
    c.shapes[name] = shape;
  }
  return c;
}

/** What a scene sees at time t: the chunks begun by then, and the last keyframe among them. */
export function tape(/** @type {Chunk[]} */ chunks, /** @type {number} */ t) {
  const shown = chunks.filter((c) => c.t0 <= t);
  /** @type {Tape} */
  const out = { t, key: null, chunks: shown };
  for (const c of shown) if (c.key) out.key = c;
  return out;
}

/** The index of the first chunk still needed at t: the last keyframe at or before t, or the first
 *  chunk that ends after t - span, whichever is earlier. */
export function needed(/** @type {Chunk[]} */ chunks, /** @type {number} */ t, /** @type {number} */ span) {
  let key = Infinity, recent = chunks.length;
  chunks.forEach((c, i) => {
    if (c.key && c.t0 <= t) key = i;
    if (c.t1 > t - span && recent === chunks.length) recent = i;
  });
  return Math.min(key, recent);
}

/**
 * Plays a server's chunks on `canvas`, drawing `scene(scr, look, tape, input)` at every frame.
 * `speed` is a multiple of real time, where real time is `perSecond` world units a second (1000 if
 * the world counts in ms); `unit` names them in the status line, drawn over the bottom 9 rows.
 * Returns `send(msg)`, a message to the source, and the clock as it stands (`t`, `speed`, `held`).
 * @param {{canvas: HTMLCanvasElement, scene: Scene, look?: string, w?: number, h?: number,
 *   speed?: number, perSecond?: number, ahead?: number, span?: number, unit?: string,
 *   status?: boolean, base?: string}} options
 */
export function live({ canvas, scene, look = "arcade", w = 320, h = 180, speed = 1, perSecond = 1,
  ahead = 2, span = 0, unit = "", status = true, base = "" }) {
  const scr = screen(w, h), L = LOOKS[look];
  /** @type {Chunk[]} */ let chunks = [];
  /** @type {number[] | null} */ let pick = null;
  let t = NaN, playing = true, ended = false, pulling = false, tick = 0, last = performance.now();
  const send = (/** @type {any} */ msg) => fetch(`${base}/act`, { method: "POST", body: JSON.stringify(msg) });
  const end = () => (chunks.length ? chunks[chunks.length - 1].t1 : t);

  async function pull() {
    if (pulling) return;
    pulling = true;
    try {
      while (!ended && (isNaN(t) || end() < t + ahead * speed * perSecond)) {
        const res = await fetch(`${base}/next`);
        if (res.status === 204) ended = true;
        else {
          chunks.push(decode(await res.arrayBuffer()));
          if (isNaN(t)) t = chunks[0].t0;
        }
      }
    } finally {
      pulling = false;
    }
  }

  function frame(/** @type {number} */ now) {
    const dt = Math.min((now - last) / 1000, 0.25); // a hidden tab never leaps
    last = now;
    const behind = playing && t + speed * perSecond * dt > end();
    if (playing && !isNaN(t)) t = Math.min(t + speed * perSecond * dt, end());
    if (!isNaN(t)) chunks = chunks.slice(needed(chunks, t, span));
    pull();
    if (!isNaN(t)) {
      scene(scr, L, tape(chunks, t), { step: 0, tick: tick++, pick, t, speed, playing });
      if (status) {
        const state = !playing ? "PAUSED" : ended && t >= end() ? "END" : behind ? "COMPUTING" : "";
        scr.rect(0, h - 9, w, 9, L.paper);
        scr.text(`T ${t.toFixed(1)} ${unit}  ×${speed}  ${state}`, 2, h - 8, L.dim);
      }
      blit(scr, canvas, L.palette);
    }
    requestAnimationFrame(frame);
  }

  canvas.addEventListener("click", (e) => send({ pick: (pick = at(e, canvas)), t }));
  addEventListener("keydown", (e) => {
    if (e.key === " ") (playing = !playing), e.preventDefault();
    if (e.key === "]" || e.key === "ArrowRight") speed = Math.min(speed * 2, 1024);
    if (e.key === "[" || e.key === "ArrowLeft") speed = Math.max(speed / 2, 1 / 1024);
  });
  fetch(`${base}/start`, { method: "POST" }).then(() => (pull(), requestAnimationFrame(frame)));
  return { send, get t() { return t; }, get held() { return chunks.length; }, get speed() { return speed; } };
}
