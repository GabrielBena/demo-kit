"""demo-kit — substrate-agnostic transport + scaffolding for live research demos.

A browser watches a *real* training / dynamics loop and pokes at it: the Python side wraps your
stateful session object in a FastAPI + WebSocket transport (play loop, action dispatch, NaN-safe
JSON); the npm package ``demokit-web`` ships the matching thin-client primitives. The kit carries
NO model logic — your session calls your project's canonical functions, so the per-frame tick is
byte-identical to a training step.
"""

from demokit.serve import main, serve
from demokit.transport import ActionHandler, ExtraHandler, Hook, WsContext, dumps, finite, make_app

__version__ = "0.1.1"

__all__ = [
    "ActionHandler",
    "ExtraHandler",
    "Hook",
    "WsContext",
    "__version__",
    "dumps",
    "finite",
    "main",
    "make_app",
    "serve",
]
