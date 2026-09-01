// demokit-web — barrel.
export type { BaseMsg, SnapshotMsg, ErrorMsg, Handlers, MsgOf, GpuInfo, GpuProc } from "./types.js";
export { Net, type NetOptions } from "./net.js";
export { byId, el } from "./dom.js";
export { fitCanvas, gray } from "./canvas.js";
export {
  initUiScale,
  setUiScale,
  uiScale,
  effectiveDpr,
  canvasPoint,
  uiScaleControl,
  UI_SCALE_PRESETS,
  type UiScaleOptions,
} from "./uiscale.js";
export { drawBitGrid } from "./bitgrid.js";
export { drawChart, type ChartSpec, type Series, type Marker } from "./chart.js";
