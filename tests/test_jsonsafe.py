"""finite()/dumps() — non-finite floats become null; array-scalars unwrap without numpy."""

from __future__ import annotations

import json
import math

from demokit.transport import dumps, finite


def test_scalars_pass_through():
    assert finite(1) == 1
    assert finite(True) is True
    assert finite("NaN") == "NaN"  # strings are never touched
    assert finite(0.5) == 0.5


def test_nonfinite_floats_null():
    assert finite(math.nan) is None
    assert finite(math.inf) is None
    assert finite(-math.inf) is None


def test_nested_containers():
    obj = {"a": [1.0, math.nan, (math.inf, "x")], "b": {"c": -math.inf}}
    assert finite(obj) == {"a": [1.0, None, [None, "x"]], "b": {"c": None}}


class _Scalar:
    """A 0-d array-like (numpy/jax scalar shape) — unwrapped via .item(), no numpy import."""

    def __init__(self, v):
        self.v = v

    def item(self):
        return self.v


class _Array:
    """A >0-d array-like whose .item() raises — passed through untouched."""

    def item(self):
        raise ValueError("can only convert an array of size 1")


def test_array_scalar_duck_typing():
    assert finite(_Scalar(2.5)) == 2.5
    assert finite(_Scalar(math.nan)) is None
    a = _Array()
    assert finite(a) is a


def test_dumps_is_browser_safe():
    raw = dumps({"loss": math.nan, "ok": [1, math.inf]})
    assert "NaN" not in raw and "Infinity" not in raw
    assert json.loads(raw) == {"loss": None, "ok": [1, None]}
