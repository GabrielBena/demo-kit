# demo-kit

The **demo kit**: research demos drawn in pixel art, from a loop that really runs. Version 2 is
rebuilt light, in two halves:

- **The drawing half, `demokit-web`** (v2, here): a small pixel engine (an indexed framebuffer, a
  5 × 7 font, dithered looks) and its hosts (a browser canvas, a Slidev component, a PNG in Node).
  Plain JavaScript modules, type-checked from their JSDoc: no build step, no runtime dependency.
- **The live half, `demokit`** (Python): v2's is next, a server on Python's standard library that
  streams what a running loop does to the page. Until it lands, v1's transport (below) is unchanged.

The rule the kit keeps by shape: **the browser draws, it never computes the dynamics; the loop
runs the project's own functions.** v1 (a FastAPI transport and a TypeScript client) stays readable
and installable under its tags, `v0.1.0` to `v0.1.3`.

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
# the drawing half, in a deck or a page's project
npm install "github:GabrielBena/demo-kit#v2.0.0"

# v1, both halves, as before
pip install "demo-kit @ git+https://github.com/GabrielBena/demo-kit@v0.1.3"
npm install "github:GabrielBena/demo-kit#v0.1.3"
```

Local development: `pip install -e /path/to/demo-kit[dev]` and `npm install /path/to/demo-kit`.

## The live half today: v1's transport

v2's live half will replace this section. Until then the Python package is v1's, extracted from
the live demo of [blastema](https://github.com/GabrielBena/blastema), its reference consumer.

### The session protocol

Your session object is duck-typed; the transport needs:

- `step() -> SnapshotLike` — advance one tick (the play loop calls this at ≤ fps).
- `snapshot() -> SnapshotLike` — the current state, no advance.
- optional `initial_snapshot() -> SnapshotLike` — richer first frame (falls back to `snapshot()`).
- optional `is_playing: bool` attribute — kept in sync by play/pause.

`SnapshotLike` = a `dict` or anything with `.to_dict()`. Snapshots are sent as
`{"type": "snapshot", "data": ...}` with NaN/±Inf replaced by `null` (browsers' strict
`JSON.parse` rejects bare `NaN` — the kit never lets that frame-drop happen).

### Server usage

```python
from pathlib import Path
from demokit.transport import make_app
from demokit.serve import main

ACTIONS = {
    "reset": lambda s, msg: s.reset(int(msg.get("seed", 0))),
    "set_task": lambda s, msg: s.set_task(str(msg.get("name", ""))),
    # ... every entry: (session, msg) -> SnapshotLike | None
}


def app():
    return make_app(
        MySession,  # zero-arg factory; one session per connection
        actions=ACTIONS,
        web_dist=Path(__file__).parent / "web" / "dist",
    )


if __name__ == "__main__":
    main(app, description="my live demo")
```

Built-in actions: `play`, `pause` (re-sends a snapshot), `step`. Anything the table shouldn't
handle synchronously (long-running trains, device picks) goes through `extra_ws_handler`, an async
hook that runs *first* and can swallow any action; `on_connect`/`on_disconnect` bracket the
connection. See `demokit/transport.py` docstrings for the `WsContext` surface.

`demokit.gpu` gives `list_gpus()` (per-card occupancy incl. process owners) and
`pick_free_gpu(name_match=..., free_mem_ceil_mib=...)` — an *etiquette* picker: only cards whose
name matches the allowlist, with no compute process and low resident memory, are ever auto-picked.
Force-picking any card is a deliberate human choice via `gpu_by_index`.

### The launcher

`templates/run-demo.sh` is a parameterized one-command deploy (env auto-detect, sidecar server
deps so the base env stays clean, npm build on demand, CPU-pinned server). Consumers **vendor a
copy**, fill the config block at the top, and keep the provenance header pointing back here.

## Development

```bash
pip install -e .[dev]
pytest -q            # transport + gpu + json-safety + the agnosticism gate
ruff check . && ruff format --check .
npm ci               # the type checker only
npm run check        # tsc over the JSDoc types, no output
npm test             # node --test: the engine
```

`tests/test_agnostic.py` is a red-test gate keeping the kit substrate-agnostic: no consumer
project's vocabulary may appear in kit sources. If you're adding something that needs a consumer
term, it belongs in the consumer.
