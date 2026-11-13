"""The live half: a running loop's chunks, streamed to a page that plays them.

A source is a generator the project writes: each item is one chunk, what happened over a span of
world time ``[t0, t1)``, encoded by `chunk` as named arrays. The page (``web/live.js``) pulls the
next chunk whenever its buffer runs short, plays world time at a steady pace and draws a scene at
each frame; the loop never waits on the page, and the page never computes the dynamics. A chunk
marked ``key`` holds the state as a whole (a keyframe), the others only what changed, so a page
can start anywhere and keep little.

Python's standard library only: arrays are anything with the buffer protocol (a NumPy array, an
``array.array``), sent as their raw bytes, little-endian.

Wire format of a chunk::

    u32 n, little-endian | n bytes of JSON header | padding to 8 | each array, padded to 8
    header = {"t0", "t1", "key", "meta", "arrays": [[name, dtype, shape, offset, nbytes], ...]}
    an array's offset counts from the first array's start (4 + n, rounded up to 8)
"""

from __future__ import annotations

import json
import queue
import struct
import sys
import threading
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

# ---[ Chunks ]-------------------------------------------------------------------------------------

# memoryview's format letter and item size -> the name of the JavaScript typed array that reads it.
_DTYPES = {
    ("f", 4): "float32",
    ("d", 8): "float64",
    ("b", 1): "int8",
    ("B", 1): "uint8",
    ("?", 1): "uint8",
    ("h", 2): "int16",
    ("H", 2): "uint16",
    ("i", 4): "int32",
    ("I", 4): "uint32",
    ("l", 4): "int32",
    ("L", 4): "uint32",
}
_FORMATS: dict[str, Any] = {"float32": "f", "float64": "d", "int8": "b", "uint8": "B", "int16": "h"}
_FORMATS |= {"uint16": "H", "int32": "i", "uint32": "I"}


def _pad(n: int) -> int:
    return -n % 8


def chunk(t0: float, t1: float, *, key: bool = False, meta: dict | None = None, **arrays) -> bytes:
    """One chunk: what happened over ``[t0, t1)``, as named arrays, ready to send.

    >>> from array import array
    >>> data = chunk(0.0, 100.0, who=array("i", [3, 7]), when=array("f", [12.5, 80.0]))
    >>> decode(data)[1]["who"].tolist()
    [3, 7]
    """
    assert sys.byteorder == "little", "the wire is little-endian, as every JavaScript engine is"
    views, entries, offset = [], [], 0
    for name, value in arrays.items():
        view = memoryview(value)
        if not view.c_contiguous:
            raise ValueError(f"{name}: not contiguous (copy it first)")
        dtype = _DTYPES.get((view.format.lstrip("<=@"), view.itemsize))
        if dtype is None:
            raise ValueError(f"{name}: format {view.format!r} has no typed array (send 32 bits)")
        views.append(view.cast("B"))
        entries.append([name, dtype, list(view.shape or ()), offset, view.nbytes])
        offset += view.nbytes + _pad(view.nbytes)
    head = {"t0": t0, "t1": t1, "key": key, "meta": meta or {}, "arrays": entries}
    text = json.dumps(head, separators=(",", ":")).encode()
    out = bytearray(struct.pack("<I", len(text)) + text)
    out += bytes(_pad(len(out)))  # the arrays start at the next multiple of 8, offsets from there
    for view in views:
        out += view
        out += bytes(_pad(len(view)))
    return bytes(out)


def decode(data: bytes) -> tuple[dict, dict[str, memoryview]]:
    """A chunk's header and its arrays, each a memoryview of its shape (to read a chunk back)."""
    (n,) = struct.unpack_from("<I", data)
    head = json.loads(data[4 : 4 + n])
    start = 4 + n + _pad(4 + n)
    whole, arrays = memoryview(data), {}
    for name, dtype, shape, offset, nbytes in head["arrays"]:
        view = whole[start + offset : start + offset + nbytes]
        nd = len(shape) > 1 and nbytes > 0  # memoryview cannot shape an empty array
        arrays[name] = view.cast(_FORMATS[dtype], shape) if nd else view.cast(_FORMATS[dtype])
    return head, arrays


# ---[ The server ]---------------------------------------------------------------------------------

WEB = Path(__file__).parent / "web"  # the kit's own modules, served under /kit/
_TYPES = {".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript"}
_TYPES |= {".css": "text/css", ".json": "application/json", ".png": "image/png"}

Source = Callable[["queue.SimpleQueue[dict]"], Iterator[bytes]]


class _Run:
    """The source of the page that started last, and the messages its page sent."""

    def __init__(self, start: Source):
        self.start, self.lock = start, threading.Lock()
        self.chunks: Iterator[bytes] | None = None
        self.inbox: queue.SimpleQueue[dict] = queue.SimpleQueue()

    def restart(self):
        with self.lock:
            if self.chunks is not None and hasattr(self.chunks, "close"):
                self.chunks.close()  # type: ignore[union-attr]
            self.inbox = queue.SimpleQueue()
            self.chunks = self.start(self.inbox)

    def next(self) -> bytes | None:
        with self.lock:
            return None if self.chunks is None else next(self.chunks, None)


def serve(start: Source, *, page: Path, port: int = 8170, host: str = "127.0.0.1", quiet=False):
    """Serve a live page: ``page`` (a folder holding ``index.html``) and the chunks of ``start``.

    ``start(inbox)`` is called each time a page loads and returns that page's chunks; ``inbox``
    holds what the page sends (a click, a key), for the source to read between chunks. Routes:
    ``POST /start`` (a fresh run), ``GET /next`` (the next chunk; 204 once the source ends),
    ``POST /act`` (a JSON message into the inbox), ``/kit/...`` (the kit's modules), the rest from
    ``page``. Bound to localhost by default: reach it from elsewhere through ``ssh -L``.
    """
    server = make_server(start, page=page, port=port, host=host)
    if not quiet:
        print(f"demokit: http://{host}:{server.server_address[1]}  (Ctrl-C stops)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def make_server(start: Source, *, page: Path, port: int = 0, host: str = "127.0.0.1"):
    """The server `serve` runs, not yet serving (port 0 picks a free one; for tests)."""
    run, roots = _Run(start), {"": Path(page).resolve(), "kit/": WEB.resolve()}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # quiet: a page pulls many chunks
            pass

        def _send(self, code: int, body: bytes = b"", kind: str = "application/octet-stream"):
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if self.path == "/start":
                run.restart()
            elif self.path == "/act":
                run.inbox.put(json.loads(body or b"{}"))
            else:
                return self._send(404)
            self._send(204)

        def do_GET(self):
            path = self.path.split("?")[0].lstrip("/")
            if path == "next":
                data = run.next()
                return self._send(204) if data is None else self._send(200, data)
            prefix = "kit/" if path.startswith("kit/") else ""
            root = roots[prefix]
            file = (root / (path[len(prefix) :] or "index.html")).resolve()
            if not file.is_relative_to(root) or not file.is_file():
                return self._send(404)
            self._send(200, file.read_bytes(), _TYPES.get(file.suffix, "application/octet-stream"))

    return ThreadingHTTPServer((host, port), Handler)
