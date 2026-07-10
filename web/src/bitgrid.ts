// Pixel-strip heatmap for [case_n, bits] grids (cols = cases, rows = bits).

import { fitCanvas, gray } from "./canvas.js";

/** Draw a [case_n, bits] grid as a pixel strip, optional error overlay (red tint where
 *  errGrid[c][b] is truthy) + active-case highlight box. */
export function drawBitGrid(
  canvas: HTMLCanvasElement,
  grid: number[][],
  activeCase: number,
  errGrid?: number[][],
): void {
  const { ctx, w, h } = fitCanvas(canvas);
  const nCase = grid.length;
  const nBit = grid[0]?.length ?? 1;
  const cw = w / nCase;
  const ch = h / nBit;
  for (let c = 0; c < nCase; c++) {
    for (let b = 0; b < nBit; b++) {
      const v = grid[c][b];
      if (errGrid?.[c]?.[b]) {
        const g = Math.round(v * 255);
        ctx.fillStyle = `rgb(${Math.max(g, 150)},${Math.round(g * 0.3)},${Math.round(g * 0.3)})`;
      } else {
        ctx.fillStyle = gray(v);
      }
      ctx.fillRect(c * cw, b * ch, Math.ceil(cw), Math.ceil(ch));
    }
  }
  ctx.strokeStyle = "#5ad1a0";
  ctx.lineWidth = 2;
  ctx.strokeRect(activeCase * cw + 1, 1, cw - 2, h - 2);
}
