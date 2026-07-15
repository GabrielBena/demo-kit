"""The substrate-agnostic live-demo transport: FastAPI + one WebSocket per browser tab.

The transport carries **no model logic**. It wraps *your* stateful session object (one per
connection, built by ``session_factory``) and does exactly four things:

* **serialize** — every session touch runs on a per-connection single-worker executor, so the
  play loop's ``step`` and any incoming action never race, and a long science call never blocks
  the event loop;
* **play** — a background task calls ``session.step()`` at ≤ ``fps`` and streams each returned
  snapshot (dt-measured sleep, so a slow step degrades the rate gracefully instead of queueing);
* **dispatch** — one JSON object per client message, ``{"action": ..., ...}``. Order:
  ``extra_ws_handler`` first (async, may swallow anything — long-running trains, device picks,
  busy-guards live there), then the built-ins ``play``/``pause``, then the consumer's ``actions``
  table (sync handlers on the session executor; ``step`` is a default entry). Unknown actions and
  handler exceptions become ``{"type": "error", "msg": ...}`` frames — the socket stays up;
* **sanitize** — snapshots go out as ``{"type": "snapshot", "data": ...}`` through :func:`dumps`,
  which nulls non-finite floats. NEVER use ``websocket.send_json`` for demo frames: its bare
  ``NaN``/``Infinity`` tokens are valid for Python's lenient parser but a hard SyntaxError for the
  browser's strict ``JSON.parse``, which silently drops the whole frame.

Session protocol (duck-typed): ``step() -> SnapshotLike``, ``snapshot() -> SnapshotLike``,
optional ``initial_snapshot()`` (richer first frame) and ``is_playing: bool`` (kept in sync by
play/pause). ``SnapshotLike`` = a ``dict`` or anything with ``.to_dict()``.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import math
from collections.abc import Awaitable, Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

# fastapi at MODULE level (not lazy inside make_app): with `from __future__ import annotations`
# the endpoint's `websocket: WebSocket` annotation is a string that FastAPI resolves via
# get_type_hints against THIS module's globals — a lazy import would leave `WebSocket` unresolved
# and FastAPI silently rejects the /ws upgrade with HTTP 403.
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

log = logging.getLogger("demokit.transport")

# (session, msg) -> SnapshotLike | None, run on the session executor.
ActionHandler = Callable[[Any, dict], Any]
# async (ctx, action, msg) -> bool; True = handled (skips built-ins + the actions table).
ExtraHandler = Callable[["WsContext", str, dict], Awaitable[bool]]
# async (ctx) -> None; connection-lifecycle hooks.
Hook = Callable[["WsContext"], Awaitable[None]]


def finite(obj: Any) -> Any:
    """Recursively replace non-finite floats (``NaN`` / ``±Infinity``) with ``None``.

    Also unwraps 0-d array-like scalars (anything with ``.item()``, e.g. numpy/jax scalars that
    leaked into a snapshot) so they serialize — without importing numpy."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: finite(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [finite(v) for v in obj]
    if hasattr(obj, "item") and not isinstance(obj, (str, bytes, int, bool)):
        try:
            return finite(obj.item())
        except Exception:
            return obj
    return obj


def dumps(obj: Any) -> str:
    """JSON text with non-finite floats nulled — the browser-safe replacement for ``send_json``."""
    return json.dumps(finite(obj))


def _to_dict(snap: Any) -> dict:
    return snap if isinstance(snap, dict) else snap.to_dict()


class WsContext:
    """The per-connection surface handed to consumer hooks (``extra_ws_handler``/``on_*``).

    ``state`` is consumer scratch (e.g. a training-subprocess holder) — the kit never touches it.
    """

    def __init__(
        self,
        ws: WebSocket,
        session: Any,
        loop: asyncio.AbstractEventLoop,
        executor: ThreadPoolExecutor,
        fps: float,
    ):
        self.ws = ws
        self.session = session
        self.loop = loop
        self.state: dict[str, Any] = {}
        self._executor = executor
        self._fps = fps
        self._play_task: asyncio.Task | None = None

    @property
    def playing(self) -> bool:
        """Is the play loop live right now?"""
        return self._play_task is not None and not self._play_task.done()

    async def run(self, fn: Callable[..., Any], /, *args: Any) -> Any:
        """Run ``fn(*args)`` on the per-connection session executor (serialized with the play loop)."""
        return await self.loop.run_in_executor(self._executor, lambda: fn(*args))

    async def send(self, obj: dict) -> None:
        """NaN-safe send (see :func:`dumps`)."""
        await self.ws.send_text(dumps(obj))

    async def safe_send(self, obj: dict) -> None:
        """Send that never raises — for terminal frames that may fire after a disconnect."""
        with contextlib.suppress(Exception):
            await self.send(obj)

    async def send_snapshot(self, snap: Any) -> None:
        """``None``-safe snapshot frame (an action returning ``None`` sends nothing)."""
        if snap is not None:
            await self.send({"type": "snapshot", "data": _to_dict(snap)})

    def _mark_session(self, on: bool) -> None:
        if hasattr(self.session, "is_playing"):
            self.session.is_playing = on

    async def set_playing(self, on: bool, *, send_snapshot: bool = False) -> None:
        """Start/stop the play loop (idempotent). ``send_snapshot=True`` mirrors the built-in
        pause (a fresh frame so the client shows the settled state)."""
        if on:
            if not self.playing:
                self._mark_session(True)
                self._play_task = asyncio.create_task(self._play_loop())
        else:
            self._mark_session(False)
            if self._play_task is not None:
                self._play_task.cancel()
                self._play_task = None
            if send_snapshot:
                await self.send_snapshot(await self.run(self.session.snapshot))

    async def _play_loop(self) -> None:
        try:
            while True:
                t0 = self.loop.time()
                snap = await self.run(self.session.step)
                await self.send_snapshot(snap)
                dt = self.loop.time() - t0
                await asyncio.sleep(max(0.0, 1.0 / self._fps - dt))
        except asyncio.CancelledError:
            pass
        except Exception as e:  # keep the socket alive; report AND actually stop playing
            log.exception("play loop failed")
            self._mark_session(False)  # the loop is dead → reflect it (was left is_playing=True)
            await self.safe_send({"type": "error", "msg": f"play stopped: {e}"})


def make_app(
    session_factory: Callable[[], Any],
    *,
    actions: Mapping[str, ActionHandler] | None = None,
    extra_ws_handler: ExtraHandler | None = None,
    on_connect: Hook | None = None,
    on_disconnect: Hook | None = None,
    fps: float = 10.0,
    web_dist: Path | None = None,
    title: str = "live demo",
) -> FastAPI:
    """Build the demo app: ``/health``, ``/ws``, and (if ``web_dist`` exists) the static client."""
    table: dict[str, ActionHandler] = {"step": lambda s, _msg: s.step()}
    table.update(actions or {})

    app = FastAPI(title=title)

    @app.middleware("http")
    async def _no_cache(request, call_next):
        # Demo bundles use stable filenames (no content hash) — tell browsers not to cache, so a
        # plain reload always picks up a fresh build during iteration.
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        loop = asyncio.get_running_loop()
        executor = ThreadPoolExecutor(max_workers=1)  # serializes ALL session access
        session = await loop.run_in_executor(executor, session_factory)
        ctx = WsContext(websocket, session, loop, executor, fps)
        try:
            if on_connect is not None:
                await on_connect(ctx)
            # Initial frame: paused, and the (optionally richer) initial snapshot.
            ctx._mark_session(False)
            first = getattr(session, "initial_snapshot", session.snapshot)
            await ctx.send_snapshot(await ctx.run(first))

            while True:
                # A bad frame (non-JSON, or valid JSON that isn't an object) must NOT tear the
                # connection down — the contract is "handler exceptions become error frames, the
                # socket stays up". Only a real WebSocketDisconnect exits the loop.
                try:
                    msg = await websocket.receive_json()
                except WebSocketDisconnect:
                    raise
                except Exception:
                    await ctx.safe_send({"type": "error", "msg": "expected a JSON object"})
                    continue
                if not isinstance(msg, dict):
                    kind = type(msg).__name__
                    await ctx.send({"type": "error", "msg": f"expected a JSON object, got {kind}"})
                    continue
                action = str(msg.get("action"))

                # ONE try/except around ALL dispatch — the consumer's extra_ws_handler included (it
                # was previously UNGUARDED, so a raise there tore the connection down and killed any
                # in-flight train). Every failure becomes an error frame; the socket lives.
                try:
                    # Consumer-first: trains, device picks, busy-guards — anything async or stateful.
                    if extra_ws_handler is not None and await extra_ws_handler(ctx, action, msg):
                        continue
                    if action == "play":
                        await ctx.set_playing(True)
                        continue
                    if action == "pause":
                        await ctx.set_playing(False, send_snapshot=True)
                        continue
                    handler = table.get(action)
                    if handler is None:
                        await ctx.send({"type": "error", "msg": f"unknown action {action!r}"})
                        continue
                    snap = await ctx.run(handler, session, msg)
                    await ctx.send_snapshot(snap)
                except WebSocketDisconnect:
                    raise
                except Exception as e:
                    log.exception("action %r failed", action)
                    await ctx.safe_send({"type": "error", "msg": f"{action}: {e}"})
        except WebSocketDisconnect:
            pass
        finally:
            if on_disconnect is not None:
                with contextlib.suppress(Exception):
                    await on_disconnect(ctx)
            await ctx.set_playing(False)
            executor.shutdown(wait=False)

    if web_dist is not None and web_dist.exists():
        app.mount("/", StaticFiles(directory=str(web_dist), html=True), name="web")
    else:

        @app.get("/")
        async def _no_build():
            return {
                "msg": "Frontend not built. Build your demo's web/ (or use its vite dev server)."
                " The WebSocket API is live at /ws.",
            }

    return app
