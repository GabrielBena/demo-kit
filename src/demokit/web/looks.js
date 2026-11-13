// @ts-check
// The looks: a palette and the roles a scene draws with, so a scene never names a colour. Every
// look keeps a cue beyond hue: a sign is a hue and, where hue fails, a pattern (dither or lines).
// `mag` and `sign` shade an area (dithered); `level` and `value` colour a cell showing one number.

import { ramp, tone, LINES } from "./screen.js";

/** @typedef {import("./screen.js").Colour} Colour */
/** @typedef {{palette: string[], paper: Colour, rule: Colour, dim: Colour, text: Colour, hot: Colour,
 *   mag: (t: number) => Colour, sign: (v: number) => Colour,
 *   level: (t: number) => Colour, value: (v: number) => Colour}} Look */

const INK = [0, 2, 3, 4, 5], POS = [0, 6, 7, 8], NEG = [0, 9, 10, 11];
const hued = (/** @type {Float32Array | null | undefined} */ m) => (/** @type {number} */ v) =>
  v >= 0 ? ramp(POS, v, m) : ramp(NEG, -v, m);

/** @type {Record<string, Look>} */
export const LOOKS = {
  // (b) ink on paper, two accents: the colour-blind pair, orange for +, blue for −.
  ink: {
    palette: ["#f3eee2", "#e3dac7", "#bdb39f", "#857c6b", "#4a443b", "#1f1d1a",
              "#f3cd8f", "#de8f05", "#8a5000", "#a6c8e4", "#0173b2", "#00375a"],
    paper: 0, rule: 1, dim: 3, text: 5, hot: 7,
    mag: (t) => ramp(INK, t), sign: hued(undefined),
    level: (t) => ramp(INK, t, null), value: hued(null),
  },
  // (a) one bit: ink or paper, every shade a dither; a negative value drawn in lines.
  mono: {
    palette: ["#ebe7da", "#1b1a17"],
    paper: 0, rule: tone(1, 0, 0.12), dim: 1, text: 1, hot: 1,
    mag: (t) => tone(1, 0, t), sign: (v) => (v >= 0 ? tone(1, 0, v) : tone(1, 0, -v, LINES)),
    level: (t) => tone(1, 0, t), value: (v) => (v >= 0 ? tone(1, 0, v) : tone(1, 0, -v, LINES)),
  },
  // (c) a fuller palette on a dark screen.
  arcade: {
    palette: ["#14161c", "#252935", "#4b5263", "#8a93a6", "#c9d1de", "#f2efe6",
              "#4a3410", "#b36b00", "#ffb340", "#0f2c40", "#1f78b4", "#8fd0ff", "#ffe066"],
    paper: 0, rule: 1, dim: 3, text: 5, hot: 12,
    mag: (t) => ramp(INK, t), sign: hued(undefined),
    level: (t) => ramp(INK, t, null), value: hued(null),
  },
};
