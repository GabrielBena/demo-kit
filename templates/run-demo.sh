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
#   ./run.sh --yes            supersede OUR OWN previous instance on the port without asking
#
# If the port is busy: a previous instance of THIS demo owned by THIS user can be killed and
# superseded (interactive [y/N] on a TTY; --yes skips the prompt; non-interactive without --yes
# refuses). Anything else on the port — another user's process (shared box: never touched) or an
# unrelated process of your own — makes the script report who/what holds it and exit.
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

HOST="${HOST:-127.0.0.1}"; PORT="${PORT:-$DEFAULT_PORT}"; FORCE_BUILD=0; ASSUME_YES=0
while [ $# -gt 0 ]; do
  case "$1" in
    --port) PORT="$2"; shift 2;;
    --host) HOST="$2"; shift 2;;
    --build) FORCE_BUILD=1; shift;;
    --yes|-y) ASSUME_YES=1; shift;;
    -h|--help) sed -n '2,27p' "$0"; exit 0;;
    *) echo "unknown arg: $1 (try --help)"; exit 1;;
  esac
done

# --- port pre-flight: supersede OUR OWN previous instance of THIS demo — never anything else --
# Etiquette is deliberate and narrow (shared boxes): a co-tenant's listener is NEVER touched, and
# neither is an unrelated process of your own — the kill surface is exactly "my previous
# `python -m $DEMO_MODULE`". Confirmed on a TTY; --yes for scripted redeploys; non-TTY without
# --yes refuses (a nohup'd relaunch can never silently kill anything).
free_port_or_die() {
  command -v lsof >/dev/null 2>&1 || return 0  # cannot inspect -> let the bind fail loudly
  local pids me pid owner args
  pids="$(lsof -ti "tcp:$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  [ -z "$pids" ] && return 0
  me="$(id -un)"
  for pid in $pids; do
    owner="$(ps -o user= -p "$pid" 2>/dev/null | tr -d ' ')"
    args="$(ps -o args= -p "$pid" 2>/dev/null || true)"
    if [ "$owner" != "$me" ]; then
      { echo "✗ port $PORT is held by pid $pid (user: ${owner:-?}) — someone else's process."
        echo "  Never superseding another user's work; pick another port: ./run.sh --port $((PORT + 1))"; } >&2
      exit 1
    fi
    case "$args" in
      *"-m $DEMO_MODULE"*) ;;  # our own previous instance -> eligible
      *)
        { echo "✗ port $PORT is held by YOUR pid $pid, but it is not this demo:"
          echo "    ${args:-<no cmdline>}"
          echo "  Not killing an unrelated process; stop it yourself or pick another port."; } >&2
        exit 1;;
    esac
  done
  echo "• port $PORT: a previous $DEMO_MODULE instance is running (pid(s): $(echo "$pids" | tr '\n' ' '))"
  if [ "$ASSUME_YES" = 1 ]; then
    echo "  --yes → superseding it."
  elif [ -t 0 ]; then
    printf "  kill it and redeploy here? [y/N] "
    read -r reply
    case "$reply" in y|Y|yes|YES) ;; *) echo "  keeping it; aborting."; exit 1;; esac
  else
    echo "  non-interactive and no --yes → refusing to kill. Re-run with --yes to supersede." >&2
    exit 1
  fi
  # shellcheck disable=SC2086 — pids is a deliberate word-split list of OUR OWN pids
  kill $pids 2>/dev/null || true
  for _ in $(seq 20); do  # up to ~6 s for a graceful TERM + port release
    sleep 0.3
    [ -z "$(lsof -ti "tcp:$PORT" -sTCP:LISTEN 2>/dev/null || true)" ] && break
  done
  if [ -n "$(lsof -ti "tcp:$PORT" -sTCP:LISTEN 2>/dev/null || true)" ]; then
    echo "  still listening after TERM → SIGKILL"
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
    sleep 0.5
  fi
  echo "  superseded ✓"
}

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

# 4. Serve (superseding our own previous instance on the port, with consent — see pre-flight).
free_port_or_die
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "────────────────────────────────────────────"
echo "  live demo · $DEMO_MODULE"
echo "  local:   http://localhost:$PORT"
[ "$HOST" = "0.0.0.0" ] && echo "  network: http://${IP:-<ip>}:$PORT   (host: $(hostname))"
echo "  stop:    Ctrl-C"
echo "────────────────────────────────────────────"
exec env "${EXTRA_ENV[@]}" PYTHONPATH="$PYTHONPATH" \
  "$PY" -m "$DEMO_MODULE" --host "$HOST" --port "$PORT"
