// @ts-check
// A screen in the browser: blitted to a canvas one pixel for one (CSS scales it, pixelated, so the
// pixels stay square at any size), redrawn by a loop at a few frames a second, and a pointer read
// back in the screen's own pixels.

/** @type {WeakMap<string[], Uint8ClampedArray>} */
const RGBA = new WeakMap();
const rgba = (/** @type {string[]} */ palette) => {
  let out = RGBA.get(palette);
  if (!out) {
    out = Uint8ClampedArray.from(palette.flatMap((c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16)).concat(255)));
    RGBA.set(palette, out);
  }
  return out;
};

/** Draws `scr` on `canvas` through `palette`. */
export function blit(/** @type {{w: number, h: number, px: Uint8Array}} */ scr, /** @type {HTMLCanvasElement} */ canvas, /** @type {string[]} */ palette) {
  if (canvas.width !== scr.w || canvas.height !== scr.h) (canvas.width = scr.w), (canvas.height = scr.h);
  const ctx = /** @type {CanvasRenderingContext2D} */ (canvas.getContext("2d"));
  const img = ctx.createImageData(scr.w, scr.h), lut = rgba(palette);
  for (let i = 0; i < scr.px.length; i++) img.data.set(lut.subarray(4 * scr.px[i], 4 * scr.px[i] + 4), 4 * i);
  ctx.putImageData(img, 0, 0);
}

/** Calls `frame(tick)` `fps` times a second, tick counting from 0; returns the stop. */
export function loop(/** @type {(tick: number) => void} */ frame, fps = 10) {
  let tick = 0;
  const id = setInterval(() => frame(tick++), 1000 / fps);
  return () => clearInterval(id);
}

/** The screen pixel under a pointer event on the canvas, its picture fitted inside its box and
 *  centred (CSS object-fit: contain). */
export function at(/** @type {MouseEvent} */ e, /** @type {HTMLCanvasElement} */ canvas) {
  const r = canvas.getBoundingClientRect(), k = Math.min(r.width / canvas.width, r.height / canvas.height);
  const x0 = r.left + (r.width - k * canvas.width) / 2, y0 = r.top + (r.height - k * canvas.height) / 2;
  return [Math.floor((e.clientX - x0) / k), Math.floor((e.clientY - y0) / k)];
}
