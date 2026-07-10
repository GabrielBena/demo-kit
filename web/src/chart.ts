// Canvas line chart — series vs x, with optional vertical event markers.
// Dumb by design: no scales/log tricks; pre-transform values in the caller if needed.

import { fitCanvas } from "./canvas.js";

export interface Series {
  values: (number | null | undefined)[]; // same length as xs (else the series is skipped)
  color: string;
  width?: number;
  dash?: number[];
}

export interface Marker {
  x: number;
  color: string;
}

export interface ChartSpec {
  xs: number[];
  series: Series[];
  markers?: Marker[];
  /** Fixed y range; default = min/max over finite values with 5% pad. */
  yDomain?: [number, number];
  /** Horizontal gridline positions; default = 3 lines over the domain. */
  yTicks?: number[];
  /** Pin out-of-domain values to the box edge instead of drawing outside. */
  clampY?: boolean;
}

const GRID = "#232b38";
const LABEL = "#5a6472";

export function drawChart(canvas: HTMLCanvasElement, spec: ChartSpec): void {
  const { ctx, w, h } = fitCanvas(canvas);
  const xs = spec.xs;
  if (xs.length < 2) return;

  const padL = 34;
  const padR = 8;
  const padT = 8;
  const padB = 16;
  const x0 = xs[0];
  const x1 = Math.max(xs[xs.length - 1], x0 + 1);

  let [ymin, ymax] = spec.yDomain ?? [Infinity, -Infinity];
  if (!spec.yDomain) {
    for (const s of spec.series) {
      if (s.values.length !== xs.length) continue;
      for (const v of s.values) {
        if (v == null || !isFinite(v)) continue;
        if (v < ymin) ymin = v;
        if (v > ymax) ymax = v;
      }
    }
    if (!isFinite(ymin) || !isFinite(ymax)) return;
    const pad = (ymax - ymin || 1) * 0.05;
    ymin -= pad;
    ymax += pad;
  }

  const px = (x: number) => padL + ((x - x0) / (x1 - x0)) * (w - padL - padR);
  const py = (y: number) => padT + ((ymax - y) / (ymax - ymin)) * (h - padT - padB);

  // Grid + y labels.
  ctx.strokeStyle = GRID;
  ctx.fillStyle = LABEL;
  ctx.lineWidth = 1;
  ctx.font = "10px ui-monospace, monospace";
  const ticks = spec.yTicks ?? [ymin, (ymin + ymax) / 2, ymax];
  for (const yv of ticks) {
    const y = py(yv);
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(w - padR, y);
    ctx.stroke();
    ctx.fillText(fmt(yv), 2, y + 3);
  }

  // Event markers.
  if (spec.markers?.length) {
    ctx.setLineDash([3, 3]);
    for (const m of spec.markers) {
      if (m.x < x0 || m.x > x1) continue;
      ctx.strokeStyle = m.color;
      ctx.globalAlpha = 0.7;
      ctx.beginPath();
      ctx.moveTo(px(m.x), padT);
      ctx.lineTo(px(m.x), h - padB);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
    ctx.setLineDash([]);
  }

  const clamp = (y: number) => Math.max(ymin, Math.min(ymax, y));
  for (const s of spec.series) {
    if (s.values.length !== xs.length) continue;
    ctx.strokeStyle = s.color;
    ctx.lineWidth = s.width ?? 1.5;
    ctx.setLineDash(s.dash ?? []);
    ctx.beginPath();
    let pen = false; // null/non-finite values gap the line
    for (let i = 0; i < xs.length; i++) {
      const v = s.values[i];
      if (v == null || !isFinite(v)) {
        pen = false;
        continue;
      }
      const x = px(xs[i]);
      const y = py(spec.clampY ? clamp(v) : v);
      if (!pen) {
        ctx.moveTo(x, y);
        pen = true;
      } else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }
  ctx.setLineDash([]);
}

function fmt(v: number): string {
  const a = Math.abs(v);
  if (a >= 100 || a === 0) return v.toFixed(0);
  if (a >= 1) return v.toFixed(1);
  if (a >= 0.01) return v.toFixed(2);
  return v.toExponential(0);
}
