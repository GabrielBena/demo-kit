// dpr-aware canvas sizing + shared color helpers.

/** Size the bitmap to the canvas's CSS display size × devicePixelRatio and return a cleared ctx.
 *  CONTRACT: every canvas passed here MUST have a CSS-pinned display size (absolute-fill, a fixed
 *  height rule, …). An UNSTYLED canvas displays at its attribute size, so clientWidth×dpr feeds
 *  back and the canvas GROWS by dpr on every call — the runaway-diagram bug. */
export function fitCanvas(canvas: HTMLCanvasElement): {
  ctx: CanvasRenderingContext2D;
  w: number;
  h: number;
} {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth || 300;
  const h = canvas.clientHeight || 150;
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
  }
  const ctx = canvas.getContext("2d")!;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  return { ctx, w, h };
}

/** Activation → grayscale (dark page-friendly: 24..234). */
export function gray(a: number): string {
  const g = Math.max(0, Math.min(255, Math.round(24 + a * 210)));
  return `rgb(${g},${g},${g})`;
}
