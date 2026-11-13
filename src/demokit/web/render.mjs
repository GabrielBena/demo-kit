// @ts-check
// A scene drawn headless, to see it without a browser and to check it (node only):
//   node render.mjs <scenes.js> <scene> <data.json> <out.png> [--step k] [--tick k] [--pick x,y]
//                   [--look arcade] [--size 640x360] [--scale 3]
// A scene is `scene(scr, look, data, input)`: it draws one picture of `data` on the screen, in the
// look's roles; `input` is what its host passes (a slide's clicks as `step`, the frames since as
// `tick`, the pixel last clicked as `pick`).

import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { parseArgs } from "node:util";
import { screen } from "./screen.js";
import { LOOKS } from "./looks.js";
import { png } from "./png.js";

/** @typedef {import("./screen.js").Screen} Screen */
/** @typedef {import("./looks.js").Look} Look */
/** @typedef {(scr: Screen, look: Look, data: any, input: any) => void} Scene */

/** The screen `scene` draws from `data` and `input`, in the look named `look`. */
export function draw(/** @type {Scene} */ scene, /** @type {any} */ data, input = {}, { look = "arcade", w = 640, h = 360 } = {}) {
  const scr = screen(w, h);
  scene(scr, LOOKS[look], data, { step: 0, tick: 0, pick: null, ...input });
  return scr;
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const { values: o, positionals } = parseArgs({
    allowPositionals: true,
    options: {
      step: { type: "string", default: "0" },
      tick: { type: "string", default: "0" },
      pick: { type: "string" },
      look: { type: "string", default: "arcade" },
      size: { type: "string", default: "640x360" },
      scale: { type: "string", default: "3" },
    },
  });
  const [module, name, dataPath, out] = positionals;
  if (!out) throw new Error("usage: node render.mjs <scenes.js> <scene> <data.json> <out.png> [--step k] [--tick k] ...");
  const scenes = await import(pathToFileURL(resolve(module)).href);
  const data = JSON.parse(readFileSync(dataPath, "utf8"));
  const [w, h] = o.size.split("x").map(Number);
  const pick = o.pick ? o.pick.split(",").map(Number) : null;
  const scr = draw(scenes[name], data, { step: +o.step, tick: +o.tick, pick }, { look: o.look, w, h });
  writeFileSync(out, png(scr, LOOKS[o.look].palette, +o.scale));
}
