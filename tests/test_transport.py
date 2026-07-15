"""Transport semantics — the contract consumers build on, pinned over the REAL /ws socket.

These tests encode behaviors extracted from the reference consumer's demo server verbatim:
initial-frame-on-connect, pause-sends-a-snapshot, extra-handler-runs-first, action errors keep the
socket alive, and NaN → null on the wire (the strict-JSON.parse frame-drop trap)."""

from __future__ import annotations

import json
import math

import pytest

pytest.importorskip("starlette")
pytest.importorskip("httpx")

from starlette.testclient import TestClient

from demokit.transport import make_app


class FakeSession:
    def __init__(self):
        self.is_playing = False
        self.n = 0
        self.x = 0.0

    def snapshot(self):
        return {"step": self.n, "is_playing": self.is_playing, "x": self.x}

    def initial_snapshot(self):
        return {**self.snapshot(), "initial": True}

    def step(self):
        self.n += 1
        return self.snapshot()

    def set_x(self, x: float):
        self.x = x
        return self.snapshot()


def _client(**kw) -> TestClient:
    return TestClient(make_app(FakeSession, **kw))


def _recv(ws) -> dict:
    return json.loads(ws.receive_text())


def test_initial_frame_is_snapshot_paused():
    with _client().websocket_connect("/ws") as ws:
        first = _recv(ws)
        assert first["type"] == "snapshot"
        assert first["data"]["initial"] is True  # initial_snapshot() preferred over snapshot()
        assert first["data"]["is_playing"] is False


def test_step_is_a_default_action():
    with _client().websocket_connect("/ws") as ws:
        _recv(ws)
        ws.send_json({"action": "step"})
        assert _recv(ws)["data"]["step"] == 1
        ws.send_json({"action": "step"})
        assert _recv(ws)["data"]["step"] == 2


def test_actions_table_dispatch_with_args():
    actions = {"set_x": lambda s, msg: s.set_x(float(msg.get("x", 0.0)))}
    with _client(actions=actions).websocket_connect("/ws") as ws:
        _recv(ws)
        ws.send_json({"action": "set_x", "x": 3.5})
        assert _recv(ws)["data"]["x"] == 3.5


def test_unknown_action_is_an_error_frame():
    with _client().websocket_connect("/ws") as ws:
        _recv(ws)
        ws.send_json({"action": "zap"})
        msg = _recv(ws)
        assert msg == {"type": "error", "msg": "unknown action 'zap'"}


def test_action_exception_reports_and_keeps_socket_alive():
    def boom(s, msg):
        raise RuntimeError("kaboom")

    with _client(actions={"boom": boom}).websocket_connect("/ws") as ws:
        _recv(ws)
        ws.send_json({"action": "boom"})
        msg = _recv(ws)
        assert msg["type"] == "error" and msg["msg"].startswith("boom: kaboom")
        ws.send_json({"action": "step"})  # the socket survived
        assert _recv(ws)["data"]["step"] == 1


def test_none_returning_action_sends_nothing():
    actions = {"quiet": lambda s, msg: None}
    with _client(actions=actions).websocket_connect("/ws") as ws:
        _recv(ws)
        ws.send_json({"action": "quiet"})
        ws.send_json({"action": "step"})
        assert _recv(ws)["data"]["step"] == 1  # the next frame is the step, not a quiet-frame


def test_nan_becomes_null_on_the_wire():
    actions = {"nanify": lambda s, msg: s.set_x(math.nan)}
    with _client(actions=actions).websocket_connect("/ws") as ws:
        _recv(ws)
        ws.send_json({"action": "nanify"})
        raw = ws.receive_text()
        assert "NaN" not in raw  # bare NaN would frame-drop in the browser's JSON.parse
        assert json.loads(raw)["data"]["x"] is None


def test_play_streams_then_pause_acks_with_snapshot():
    with _client(fps=200.0).websocket_connect("/ws") as ws:
        _recv(ws)
        ws.send_json({"action": "play"})
        a, b = _recv(ws), _recv(ws)  # at least two live frames
        assert a["data"]["is_playing"] and b["data"]["step"] > a["data"]["step"] >= 1
        ws.send_json({"action": "pause"})
        # In-flight play frames may precede the ack; the FIRST is_playing=False frame is the ack.
        for _ in range(200):
            msg = _recv(ws)
            if msg["data"]["is_playing"] is False:
                break
        else:
            pytest.fail("pause never acked with a settled snapshot")
        settled = msg["data"]["step"]
        ws.send_json({"action": "step"})  # after the ack the loop is dead: exactly one increment
        assert _recv(ws)["data"]["step"] == settled + 1


def test_extra_ws_handler_runs_first_and_swallows():
    async def extra(ctx, action, msg):
        if action == "step":  # hijack even a built-in/default action
            await ctx.send({"type": "custom", "note": "swallowed"})
            return True
        return False

    actions = {"peek": lambda s, msg: s.snapshot()}
    with _client(actions=actions, extra_ws_handler=extra).websocket_connect("/ws") as ws:
        _recv(ws)
        ws.send_json({"action": "step"})
        assert _recv(ws) == {"type": "custom", "note": "swallowed"}
        ws.send_json({"action": "peek"})
        assert _recv(ws)["data"]["step"] == 0  # the swallowed step never touched the session


def test_connect_and_disconnect_hooks_fire():
    events: list[str] = []

    async def on_connect(ctx):
        ctx.state["train"] = {"active": False}  # the consumer scratch-state pattern
        events.append("connect")

    async def on_disconnect(ctx):
        events.append(f"disconnect:{ctx.state['train']['active']}")

    with _client(on_connect=on_connect, on_disconnect=on_disconnect).websocket_connect("/ws") as ws:
        _recv(ws)
        assert events == ["connect"]
    assert events == ["connect", "disconnect:False"]


def test_health_and_unbuilt_frontend_hint():
    c = _client()
    assert c.get("/health").json() == {"ok": True}
    r = c.get("/")
    assert "not built" in r.json()["msg"].lower()
    assert r.headers["Cache-Control"] == "no-cache, no-store, must-revalidate"


def test_web_dist_is_mounted_when_present(tmp_path):
    (tmp_path / "index.html").write_text("<html><body>demo</body></html>")
    c = TestClient(make_app(FakeSession, web_dist=tmp_path))
    r = c.get("/")
    assert r.status_code == 200 and "demo" in r.text


# --- connection resilience: a bad frame or a handler raise must NEVER tear the socket down --------
# (blind-review regressions, 2026-07-14: a malformed frame / non-dict JSON / unguarded extra-handler
# exception used to unwind the connection — auto-reconnect then landed in a FRESH session, silently
# resetting progress.)


def test_non_dict_frame_is_an_error_frame_not_a_teardown():
    with _client().websocket_connect("/ws") as ws:
        _recv(ws)
        ws.send_json("step")  # valid JSON, but not an object → msg.get() would have raised
        msg = _recv(ws)
        assert msg["type"] == "error" and "object" in msg["msg"]
        ws.send_json({"action": "step"})  # the socket survived
        assert _recv(ws)["data"]["step"] == 1


def test_malformed_json_frame_is_an_error_frame_not_a_teardown():
    with _client().websocket_connect("/ws") as ws:
        _recv(ws)
        ws.send_text("not json {{{")  # receive_json() raises JSONDecodeError
        assert _recv(ws)["type"] == "error"
        ws.send_json({"action": "step"})  # the socket survived
        assert _recv(ws)["data"]["step"] == 1


def test_extra_handler_exception_is_an_error_frame_not_a_teardown():
    async def extra(ctx, action, msg):
        if action == "explode":
            raise RuntimeError("boom in extra")
        return False

    with _client(extra_ws_handler=extra).websocket_connect("/ws") as ws:
        _recv(ws)
        ws.send_json({"action": "explode"})
        msg = _recv(ws)
        assert msg["type"] == "error" and "boom in extra" in msg["msg"]
        ws.send_json({"action": "step"})  # the connection survived the handler raise
        assert _recv(ws)["data"]["step"] == 1


def test_play_loop_step_error_reports_instead_of_silently_freezing():
    class Boom(FakeSession):
        def step(self):
            raise RuntimeError("step exploded")

    with TestClient(make_app(Boom, fps=200.0)).websocket_connect("/ws") as ws:
        _recv(ws)  # initial frame
        ws.send_json({"action": "play"})
        # the play loop's step() raises: the client must get an error frame, not silence + a stuck
        # is_playing=True. pause then acks with a settled snapshot showing is_playing False.
        msg = _recv(ws)
        assert msg["type"] == "error" and "play stopped" in msg["msg"]
        ws.send_json({"action": "pause"})
        assert _recv(ws)["data"]["is_playing"] is False
