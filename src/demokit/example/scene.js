// @ts-check
// The example's scene: each dot a 2 × 2 square, lit by its last flash, fading over 60 ms.

const FADE = 60; // ms

/** @param {import("../web/screen.js").Screen} scr @param {import("../web/looks.js").Look} L
 *  @param {import("../web/live.js").Tape} tape */
export function dots(scr, L, tape) {
  scr.clear(L.paper);
  scr.text("DOTS · CLICK ONE", 4, 4, L.text);
  if (!tape.key) return;
  const { x, y } = tape.key.arrays, glow = new Float32Array(x.length);
  for (const c of tape.chunks) {
    const { who, when } = c.arrays;
    for (let k = 0; k < who.length; k++)
      if (when[k] <= tape.t) glow[who[k]] = Math.max(glow[who[k]], Math.exp(-(tape.t - when[k]) / FADE));
  }
  for (let i = 0; i < x.length; i++)
    scr.rect(Math.round(x[i]), Math.round(y[i]), 2, 2, glow[i] > 0.5 ? L.hot : L.level(0.25 + 0.75 * glow[i]));
}
