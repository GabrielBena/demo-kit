# demo-kit

The **live-demo kit**: substrate-agnostic scaffolding for interactive research demos where a
browser watches a *real* training / dynamics loop run live and pokes at it. One paradigm, two
layers:

- **`demokit` (Python, pip)** — a FastAPI + WebSocket transport that wraps *your* stateful
  session object: a play loop streams JSON state snapshots at a capped fps, user actions dispatch
  to your session's methods, everything serialized on a per-connection worker so the science code
  never races. Plus a GPU-occupancy/etiquette module and a uvicorn launcher.
- **`demokit-web` (TypeScript, npm)** — the matching thin-client primitives: a typed WebSocket
  client, DOM helpers, a canvas line chart, dpr-aware canvas sizing, a bit-grid heatmap, and base
  styles. Vanilla TS, zero runtime dependencies; bring your own renderer for your substrate.

The design rule the kit enforces by shape: **the browser renders snapshots, it never computes;
the server orchestrates, it never re-implements dynamics.** Every action routes through your
session, which calls your project's canonical functions — so the per-frame tick is byte-identical
to a training step.

Extracted from the live demo of [blastema](https://github.com/GabrielBena/blastema), which is the
reference consumer.

## Install

```bash
# python (server side)
pip install "demo-kit @ git+https://github.com/GabrielBena/demo-kit@v0.1.0"

# web (client side) — in your demo's web/ dir
npm install "github:GabrielBena/demo-kit#v0.1.0"
```

Local development: `pip install -e /path/to/demo-kit[dev]` and `npm install /path/to/demo-kit`.

## The session protocol

Your session object is duck-typed; the transport needs:

- `step() -> SnapshotLike` — advance one tick (the play loop calls this at ≤ fps).
- `snapshot() -> SnapshotLike` — the current state, no advance.
- optional `initial_snapshot() -> SnapshotLike` — richer first frame (falls back to `snapshot()`).
- optional `is_playing: bool` attribute — kept in sync by play/pause.

`SnapshotLike` = a `dict` or anything with `.to_dict()`. Snapshots are sent as
`{"type": "snapshot", "data": ...}` with NaN/±Inf replaced by `null` (browsers' strict
`JSON.parse` rejects bare `NaN` — the kit never lets that frame-drop happen).

## Server usage

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
        MySession,                      # zero-arg factory; one session per connection
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

## Client usage

```ts
import { Net, byId, el, drawChart } from "demokit-web";
import "demokit-web/styles.css";

type Msg = SnapshotMsg<MySnapshot> | ErrorMsg | { type: "my_custom"; ... };
const net = new Net<Msg>({
  handlers: { snapshot: (m) => render(m.data), error: (m) => console.warn(m.msg) },
  onStatus: (up) => byId("dot").classList.toggle("up", up),
});
net.connect();
net.send({ action: "step" });
```

## The launcher

`templates/run-demo.sh` is a parameterized one-command deploy (env auto-detect, sidecar server
deps so the base env stays clean, npm build on demand, CPU-pinned server). Consumers **vendor a
copy**, fill the config block at the top, and keep the provenance header pointing back here.

## Development

```bash
pip install -e .[dev]
pytest -q            # transport + gpu + json-safety + the agnosticism gate
ruff check . && ruff format --check .
npm install && npm run build
```

`tests/test_agnostic.py` is a red-test gate keeping the kit substrate-agnostic: no consumer
project's vocabulary may appear in kit sources. If you're adding something that needs a consumer
term, it belongs in the consumer.
