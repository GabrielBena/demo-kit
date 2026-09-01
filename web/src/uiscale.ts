// UI scale — an app-level zoom for presentations. Demo layouts are sized for a dev screen (13px mono,
// ~300px sidebar); on a projector or in a screen-share they are tiny. This is "browser zoom, but one
// click, app-scoped, and it sticks".
//
// Mechanism — two halves that must agree, both reading the ONE `--ui-scale` value:
//   1. Layout (`initUiScale`): `--ui-scale` is set on :root and the app root gets
//      `width/height: calc(100% / var(--ui-scale)); transform: scale(var(--ui-scale))` — every DOM box,
//      font and canvas CSS box scales VISUALLY while layout px stay unscaled, and the viewport stays exactly
//      filled (html/body get overflow:hidden — the root IS the viewport; panels scroll internally).
//   2. Canvas density (`fitCanvas`): a transformed canvas covers clientWidth × dpr × scale device pixels, so
//      bitmaps are sized with `effectiveDpr()` = devicePixelRatio × scale — exactly what browser zoom does
//      to devicePixelRatio. Canvas-drawn text and pads scale with the rest of the UI, crisp.
//   Pointer math: getBoundingClientRect() is in VISUAL px while canvases lay out in layout px →
//   `canvasPoint` maps a MouseEvent back with the measured ratio (fraction-based hits are scale-invariant).
//
// Persisted per browser (localStorage, consumer-namespaced key). A link can pin it for a talk: `?scale=1.5`
// (wins for that load; NOT persisted, so a shared link never overwrites the viewer's own preference).

import { el } from "./dom.js";

export const UI_SCALE_PRESETS = [0.85, 1, 1.25, 1.5, 1.75, 2];
const MIN = 0.5;
const MAX = 3;

let scale = 1;
let storageKey = "demokit.uiScale";

export interface UiScaleOptions {
  /** The element that fills the viewport (the demo's `#app`). Receives the transform recipe inline. */
  root: HTMLElement;
  /** localStorage key — namespace it per demo so two demos on one origin don't share a preference. */
  storageKey?: string;
  /** The scale used when nothing is saved and no `?scale=` is in the URL (default 1 = as designed). */
  defaultScale?: number;
}

/** The current UI scale (1 = as designed). */
export function uiScale(): number {
  return scale;
}

/** devicePixelRatio × uiScale — the density a transform-scaled canvas actually covers. */
export function effectiveDpr(): number {
  return (window.devicePixelRatio || 1) * scale;
}

function clamp(s: number): number | null {
  return Number.isFinite(s) && s >= MIN && s <= MAX ? Math.round(s * 100) / 100 : null;
}

/** Apply a scale (CSS variable → layout half; `effectiveDpr` → canvas half), persist it, and fire
 *  `resize` so every canvas re-fits at the new density. Out-of-range values are ignored. */
export function setUiScale(s: number, persist = true): void {
  const v = clamp(s);
  if (v === null) return;
  scale = v;
  document.documentElement.style.setProperty("--ui-scale", String(v));
  if (persist) {
    try {
      localStorage.setItem(storageKey, String(v));
    } catch {
      /* private mode / storage blocked — the scale still applies for this page */
    }
  }
  window.dispatchEvent(new Event("resize"));
}

/** Install the mechanism on `root` and apply the initial scale (URL `?scale=` > saved > `defaultScale`).
 *  Call ONCE, before the first canvas draw. Returns the scale applied. */
export function initUiScale(opts: UiScaleOptions): number {
  storageKey = opts.storageKey ?? storageKey;
  const r = opts.root.style;
  r.width = "calc(100% / var(--ui-scale, 1))";
  r.height = "calc(100% / var(--ui-scale, 1))";
  r.transform = "scale(var(--ui-scale, 1))";
  r.transformOrigin = "0 0";
  document.documentElement.style.overflow = "hidden";
  document.body.style.overflow = "hidden";
  const fromUrl = clamp(parseFloat(new URLSearchParams(location.search).get("scale") ?? ""));
  let saved: number | null = null;
  try {
    saved = clamp(parseFloat(localStorage.getItem(storageKey) ?? ""));
  } catch {
    saved = null;
  }
  if (fromUrl !== null) setUiScale(fromUrl, false);
  else setUiScale(saved ?? clamp(opts.defaultScale ?? 1) ?? 1, false);
  return scale;
}

/** A pointer event's position in the canvas's LAYOUT px (what fitCanvas's `w`/`h` and your drawing use),
 *  whatever the UI scale. Use this instead of `e.clientX - rect.left` for canvas hit-tests. */
export function canvasPoint(canvas: HTMLCanvasElement, e: MouseEvent): { x: number; y: number } {
  const rect = canvas.getBoundingClientRect();
  const k = canvas.clientWidth ? rect.width / canvas.clientWidth : 1;
  return { x: (e.clientX - rect.left) / k, y: (e.clientY - rect.top) / k };
}

/** The topbar control: a compact preset picker (`<label class="ui-scale">`). The current value is offered
 *  even when it is not a preset (e.g. pinned by `?scale=`). Mount it once. */
export function uiScaleControl(): HTMLElement {
  const sel = el("select", {
    title:
      "UI scale — zoom the whole demo for a projector / screen-share (remembered in this browser; add ?scale=1.5 to the URL to pin it in a link)",
  }) as HTMLSelectElement;
  const fill = () => {
    const opts = UI_SCALE_PRESETS.includes(scale)
      ? UI_SCALE_PRESETS
      : [...UI_SCALE_PRESETS, scale].sort((a, b) => a - b);
    sel.replaceChildren(...opts.map((s) => el("option", { value: String(s) }, `${Math.round(s * 100)}%`)));
    sel.value = String(scale);
  };
  fill();
  sel.onchange = () => {
    setUiScale(Number(sel.value));
    fill();
  };
  return el("label", { class: "ui-scale" }, "UI ", sel);
}
