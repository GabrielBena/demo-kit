"""Uvicorn launcher helpers — so every consumer's ``__main__`` is three lines."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Any


def serve(app: Any, *, host: str = "127.0.0.1", port: int = 8000) -> None:
    """Serve a FastAPI app with the demo-standard uvicorn config (wsproto, quiet logs)."""
    try:
        import uvicorn
    except ImportError as e:  # pragma: no cover - hard dep, but a helpful message beats a trace
        raise SystemExit("uvicorn missing - install the demo-kit package with its deps") from e
    uvicorn.run(app, host=host, port=port, log_level="warning", ws="wsproto")


def main(
    app_factory: Callable[[], Any],
    *,
    description: str = "live-demo server",
    default_host: str = "127.0.0.1",
    default_port: int = 8000,
    argv: list[str] | None = None,
) -> None:
    """The standard ``python -m yourpkg.demo`` entry: ``--host``/``--port`` argparse + serve."""
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--host", default=default_host)
    ap.add_argument("--port", type=int, default=default_port)
    args = ap.parse_args(argv)
    serve(app_factory(), host=args.host, port=args.port)
