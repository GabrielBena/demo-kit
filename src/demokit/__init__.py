"""demo-kit: research demos drawn in pixel art, from a loop that really runs.

Two halves: the pixel engine and its hosts, plain JavaScript modules in ``demokit/web`` (no build),
and the live half here, Python's standard library only: a source yields chunks of what happened
(`chunk`), and `serve` streams them to a page that plays world time at a steady pace and draws a
scene at each frame. The kit holds no model: the source calls the project's own functions.
"""

from demokit.live import chunk, decode, make_server, serve

__version__ = "2.0.0"

__all__ = ["__version__", "chunk", "decode", "make_server", "serve"]
