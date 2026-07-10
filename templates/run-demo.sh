#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# demo-kit launcher TEMPLATE — vendor a copy next to your demo module, fill the
# config block, keep this provenance header:
#   vendored from demo-kit templates/run-demo.sh
#
#   ./run.sh                  build the UI if needed, then serve
#   ./run.sh --port 9000      pick a port
#   ./run.sh --host 0.0.0.0   expose on the network (default: localhost only)
#   ./run.sh --build          force-rebuild the frontend
#
# To leave it running for collaborators:  nohup ./run.sh >demo.log 2>&1 &
#
# ⚠️ SSOT LAUNCHER — humans AND agents start the demo THROUGH this script; never
#    hand-roll `python -m ...`. EXTRA_ENV below pins the server's compute (e.g.
#    JAX_PLATFORMS=cpu keeps the demo server off shared GPUs); a hand-rolled
#    launch that omits it may grab every card on the box.
#
# Env overrides:
#   DEMO_PY   python interpreter with your project's deps (auto-detected otherwise)
#   NPM       npm binary (auto-detected; only needed to (re)build the UI)
# ---------------------------------------------------------------------------
set -euo pipefail

# --- config block (edit when vendoring) ------------------------------------
DEMO_MODULE="yourpkg.demo"           # `python -m $DEMO_MODULE --host .. --port ..`
WEB_DIR_REL="web"                    # your web app, relative to this script
PY_IMPORT_CHECK="yourpkg"            # imports that must resolve in the picked python
SIDECAR_SPEC="fastapi>=0.110 uvicorn>=0.29 wsproto>=1.2"  # server deps if missing
SIDECAR_DIR_NAME=".demo-deps"        # sidecar dir, created next to the repo root
REPO_UP=2                            # repo root is this many dirs above this script
DEFAULT_PORT=8150
EXTRA_ENV=(JAX_PLATFORMS=cpu)        # exported for the server process
# ----------------------------------------------------------------------------

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$HERE"; for _ in $(seq "$REPO_UP"); do REPO="$(dirname "$REPO")"; done
WEB="$HERE/$WEB_DIR_REL"
DEPS="$(dirname "$REPO")/$SIDECAR_DIR_NAME"

HOST="${HOST:-127.0.0.1}"; PORT="${PORT:-$DEFAULT_PORT}"; FORCE_BUILD=0
while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="$2"; shift 2;;
    --host) HOST="$2"; shift 2;;
    --build) FORCE_BUILD=1; shift;;
    -h|--help) sed -n '2,22p' "$0"; exit 0;;
    *) echo "unknown arg: $1 (try --help)"; exit 1;;
  esac
done

# 1. A python with the project's deps.
PY="${DEMO_PY:-}"
if [ -z "$PY" ]; then
  c="$(command -v python || true)"
  if [ -n "$c" ] && "$c" -c "import $PY_IMPORT_CHECK" >/dev/null 2>&1; then PY="$c"; fi
fi
if [ -z "$PY" ]; then
  echo "✗ No python that imports '$PY_IMPORT_CHECK'. Activate your env, or set DEMO_PY=/path/to/python." >&2
  exit 1
fi
echo "• python: $PY"

# 2. Server deps → sidecar dir, only if missing. Never touches the base env.
export PYTHONPATH="$DEPS${PYTHONPATH:+:$PYTHONPATH}"
if ! "$PY" -c "import fastapi, uvicorn, wsproto" >/dev/null 2>&1; then
  echo "• installing server deps into $DEPS ..."
  # shellcheck disable=SC2086 — SIDECAR_SPEC is a deliberate word-split list of pip specs
  "$PY" -m pip install --target="$DEPS" $SIDECAR_SPEC >/dev/null
fi

# 3. Build the frontend if there's no build (or --build). Needs node/npm.
if [ "$FORCE_BUILD" = 1 ] || [ ! -f "$WEB/dist/index.html" ]; then
  NPM="${NPM:-$(command -v npm || true)}"
  if [ -n "$NPM" ]; then
    echo "• building frontend ($NPM) ..."
    [ -d "$WEB/node_modules" ] || "$NPM" install --prefix "$WEB"
    "$NPM" run build --prefix "$WEB"
  elif [ ! -f "$WEB/dist/index.html" ]; then
    echo "✗ No frontend build and no npm to build it. Install node, or set NPM=/path/to/npm." >&2
    exit 1
  fi
fi

# 4. Serve.
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "────────────────────────────────────────────"
echo "  live demo · $DEMO_MODULE"
echo "  local:   http://localhost:$PORT"
[ "$HOST" = "0.0.0.0" ] && echo "  network: http://${IP:-<ip>}:$PORT   (host: $(hostname))"
echo "  stop:    Ctrl-C"
echo "────────────────────────────────────────────"
exec env "${EXTRA_ENV[@]}" PYTHONPATH="$PYTHONPATH" \
  "$PY" -m "$DEMO_MODULE" --host "$HOST" --port "$PORT"
