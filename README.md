# demo-kit

The **demo kit**: research demos drawn in pixel art, from a loop that really runs. Version 2 is
rebuilt light, in two halves:

- **The drawing half, `demokit-web`** (v2, here): a small pixel engine (an indexed framebuffer, a
  5 × 7 font, dithered looks) and its hosts (a browser canvas, a Slidev component, a PNG in Node).
  Plain JavaScript modules, type-checked from their JSDoc: no build step, no runtime dependency.
- **The live half, `demokit`** (Python): a server on Python's standard library that streams what a
  running loop does to a page, which plays it at a steady pace of world time.

The rule the kit keeps by shape: **the browser draws, it never computes the dynamics; the loop
runs the project's own functions.** v1 (a FastAPI transport and a TypeScript client, extracted
from the live demo of [blastema](https://github.com/GabrielBena/blastema)) stays readable and
installable under its tags, `v0.1.0` to `v0.1.3`.

## A scene

A scene is a pure function, `scene(scr, look, data, input)`: it draws one picture of `data` on the
screen `scr`, in the roles of `look`, never naming a colour. Its host decides when to call it and
what `input` holds (a slide's clicks as `step`, the frames since as `tick`, the pixel last clicked
as `pick`).

```js
// @ts-check
/** A row of cells, each lit by its value; the clicked one framed. */
export function cells(scr, L, values, { pick }) {
  scr.clear(L.paper);
  scr.text("CELLS", 4, 4, L.text);
  scr.cells([values], 4, 16, 8, 8, (v) => L.level(v));
  if (pick) scr.box(4 + 8 * Math.floor((pick[0] - 4) / 8), 16, 8, 8, L.hot);
}
```

## The engine (`src/demokit/web/`)

- **`screen.js`**: `screen(w, h)`, every pixel a palette index, the whole scene drawn again each
  frame (immediate mode, nothing retained): `put`, `rect`, `box`, `line`, `sprite`, `cells`,
  `text`, `clear`. A colour is an index, or a `tone(a, b, t)`: two indices mixed by ordered
  dithering, so a few colours make every shade; `ramp(stops, t)` walks a list of them.
- **`font.js`**: the 5 × 7 font, the classic character-LCD shapes, ASCII and a few symbols.
- **`looks.js`**: a palette and the roles a scene draws with (`paper`, `rule`, `dim`, `text`,
  `hot`; `mag` and `sign` shade an area, `level` and `value` colour a cell). Three looks:
  **arcade** (a dark screen, the default), **ink** (ink on paper) and **mono** (one bit). Every look
  keeps a cue beyond hue: a sign is orange or blue, the colour-blind pair, and a pattern where hue
  fails.
- **`blit.js`**: a screen on a canvas, one pixel for one, scaled by CSS with square pixels;
  `loop(frame, fps)`; `at(event, canvas)`, the screen pixel under a pointer.
- **`png.js`** (Node): a screen as a PNG, scaled by a whole number.

## Hosts

**In a page**, served as static files:

```html
<canvas id="view" style="width: 100%; image-rendering: pixelated"></canvas>
<script type="module">
  import { screen } from "./web/screen.js";
  import { LOOKS } from "./web/looks.js";
  import { at, blit, loop } from "./web/blit.js";
  import { cells } from "./scenes.js";

  const canvas = document.getElementById("view"), scr = screen(320, 180), look = LOOKS.arcade;
  let pick = null, values = Array.from({ length: 16 }, () => Math.random());
  canvas.onclick = (e) => (pick = at(e, canvas));
  loop((tick) => (cells(scr, look, values, { step: 0, tick, pick }), blit(scr, canvas, look.palette)), 10);
</script>
```

**On a slide** (Slidev): register `Pixel.vue` in the deck's `setup/main.js`, then
`<Pixel :scene="cells" :data="values" :step="$clicks" />` on any slide. It redraws when the step
changes, every frame with `fps`, on a click (`pick`), and can grow a new picture out of a rectangle
of the old one (`grow`).

```js
import { defineAppSetup } from "@slidev/types";
import Pixel from "demokit-web/Pixel.vue";
export default defineAppSetup(({ app }) => app.component("Pixel", Pixel));
```

**To a PNG** (Node), to see a scene without a browser or put it in a note:

```bash
node src/demokit/web/render.mjs scenes.js cells data.json out.png --step 2 --look ink --scale 3
```

## Install

```bash
# both halves: the server, with the modules it serves
pip install "demo-kit @ git+https://github.com/GabrielBena/demo-kit@v2.0.0"

# the drawing half alone, in a deck or a page's project
npm install "github:GabrielBena/demo-kit#v2.0.0"

# v1, both halves, as before
pip install "demo-kit @ git+https://github.com/GabrielBena/demo-kit@v0.1.3"
npm install "github:GabrielBena/demo-kit#v0.1.3"
```

Local development: `pip install -e /path/to/demo-kit[dev]` and `npm install /path/to/demo-kit`.

## The live half

A **source** is a generator the project writes. Each item is one **chunk**: what happened over a
span of world time `[t0, t1)`, as named arrays. `serve` hands the chunks to a page that plays world
time at a steady pace and draws its scene at every frame. The page pulls the next chunk whenever
its buffer runs short, so the loop runs ahead of what is shown, never further than the page asks;
if the loop falls behind, the clock waits for it. Python's standard library only.

```python
from array import array
from pathlib import Path
from demokit import chunk, serve

def run(inbox):  # called at every page load; `inbox` holds what the page sends
    t = 0.0
    while True:
        who, when = step_my_model(100.0)  # the project's own code, 100 ms of world time
        yield chunk(t, t + 100.0, key=True, who=array("i", who), when=array("f", when))
        t += 100.0

serve(run, page=Path(__file__).parent / "page")  # http://127.0.0.1:8170
```

- **Arrays** are anything with the buffer protocol (a NumPy array, an `array.array`), sent as their
  raw bytes: 8, 16 and 32-bit integers, 32 and 64-bit floats.
- **Keyframes:** a chunk marked `key=True` holds the state as a whole; the others only what changed.
  The page keeps the chunks from the last keyframe before now, and back `span` world units, and
  drops the rest.
- **The inbox:** a click on the page arrives as `{"pick": [x, y], "t": t}`; `send(msg)` posts any
  message. The source reads them between chunks.
- **Routes:** `POST /start` (a fresh run), `GET /next` (the next chunk; 204 when the source ends),
  `POST /act` (a message), `/kit/...` (this kit's modules), the rest from `page`. Bound to
  localhost: from another machine, `ssh -L 8170:localhost:8170 <host>`.

The page (`page/index.html`):

```html
<canvas id="view" style="width: 100%; image-rendering: pixelated"></canvas>
<script type="module">
  import { live } from "/kit/live.js";
  import { myScene } from "./scene.js";
  live({ canvas: document.getElementById("view"), scene: myScene, perSecond: 1000, unit: "MS", span: 300 });
</script>
```

The scene's `data` is the tape at time `t`: `{t, key, chunks}`, the chunks begun by then with the
last keyframe among them, each `{t0, t1, key, meta, arrays, shapes}` with typed arrays. `input`
adds `t`, `speed` and `playing` to `step`, `tick` and `pick`. `speed` is a multiple of real time,
`perSecond` world units a second; space pauses, `]` and `[` (or the arrows) double and halve it; a
status line is drawn over the bottom 9 rows.

**A working example**, dots that wander and flash: `python -m demokit.example`, then open
`http://127.0.0.1:8170` (its source, page and scene are in `src/demokit/example/`).

## Development

```bash
pip install -e .[dev]
pytest -q            # the chunks, the server's routes, the agnosticism gate
ruff check . && ruff format --check .
npm ci               # the type checker only
npm run check        # tsc over the JSDoc types, no output
npm test             # node --test: the engine
```

`tests/test_agnostic.py` is a red-test gate keeping the kit substrate-agnostic: no consumer
project's vocabulary may appear in kit sources. If you're adding something that needs a consumer
term, it belongs in the consumer.
