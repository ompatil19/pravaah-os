#!/usr/bin/env bash
# Pravaah OS v2 — One-command launcher
# Starts Redis, RQ worker, Flask (port 8000), and Vite (port 5173) with clean teardown.
# Works on macOS (zsh/bash) and Ubuntu (bash).

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Colour helpers
# ─────────────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${CYAN}[pravaah]${NC} $*"; }
success() { echo -e "${GREEN}[pravaah]${NC} $*"; }
warn()    { echo -e "${YELLOW}[pravaah]${NC} $*"; }
error()   { echo -e "${RED}[pravaah] ERROR:${NC} $*" >&2; }

# ─────────────────────────────────────────────────────────────────────────────
# Resolve project root (directory containing this script)
# ─────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Check Python >= 3.10
# ─────────────────────────────────────────────────────────────────────────────
info "Checking Python version..."
PYTHON_BIN=""
for candidate in python3.12 python3.11 python3.10 python3 python; do
    if command -v "$candidate" &>/dev/null; then
        version=$("$candidate" -c "import sys; print(sys.version_info[:2])" 2>/dev/null || echo "(0, 0)")
        major=$(echo "$version" | tr -d '()' | cut -d',' -f1 | tr -d ' ')
        minor=$(echo "$version" | tr -d '()' | cut -d',' -f2 | tr -d ' ')
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    error "Python 3.10+ is required but not found."
    error "Install from: https://www.python.org/downloads/"
    exit 1
fi
PY_VER=$("$PYTHON_BIN" --version 2>&1)
success "Found $PY_VER"

# ─────────────────────────────────────────────────────────────────────────────
# 2. Check Node >= 18
# ─────────────────────────────────────────────────────────────────────────────
info "Checking Node.js version..."
if ! command -v node &>/dev/null; then
    error "Node.js is required but not found."
    error "Install from: https://nodejs.org/  (LTS recommended)"
    exit 1
fi
NODE_VER=$(node --version | tr -d 'v')
NODE_MAJOR=$(echo "$NODE_VER" | cut -d'.' -f1)
if [ "$NODE_MAJOR" -lt 18 ]; then
    error "Node.js >= 18 is required. Found: v${NODE_VER}"
    error "Install from: https://nodejs.org/  (LTS recommended)"
    exit 1
fi
success "Found Node.js v${NODE_VER}"

# ─────────────────────────────────────────────────────────────────────────────
# 3. Check redis-server is installed
# ─────────────────────────────────────────────────────────────────────────────
info "Checking Redis..."
if ! command -v redis-server &>/dev/null; then
    error "redis-server is required but not found."
    echo ""
    echo -e "${YELLOW}  Install Redis:${NC}"
    echo -e "${YELLOW}  macOS (Homebrew):  brew install redis${NC}"
    echo -e "${YELLOW}  Ubuntu/Debian:     sudo apt-get install -y redis-server${NC}"
    echo ""
    exit 1
fi
REDIS_VER=$(redis-server --version | awk '{print $3}' | cut -d'=' -f2)
success "Found Redis v${REDIS_VER}"

# ─────────────────────────────────────────────────────────────────────────────
# 4. Copy .env.example → .env if missing
# ─────────────────────────────────────────────────────────────────────────────
if [ ! -f .env ]; then
    warn ".env file not found. Creating from .env.example..."
    cp .env.example .env
    echo ""
    echo -e "${YELLOW}╔══════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║  ACTION REQUIRED — Set your API keys in .env before running      ║${NC}"
    echo -e "${YELLOW}╠══════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${YELLOW}║  DEEPGRAM_API_KEY   → https://console.deepgram.com/              ║${NC}"
    echo -e "${YELLOW}║  OPENROUTER_API_KEY → https://openrouter.ai/keys                 ║${NC}"
    echo -e "${YELLOW}║  FLASK_SECRET_KEY   → python -c 'import secrets; print(secrets.token_hex(32))'  ║${NC}"
    echo -e "${YELLOW}║  JWT_SECRET_KEY     → python -c 'import secrets; print(secrets.token_hex(32))'  ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    read -r -p "Press Enter after setting the keys to continue, or Ctrl+C to abort..."
fi

# Load .env into the current shell
set -a
# shellcheck disable=SC1091
source .env 2>/dev/null || true
set +a

# ─────────────────────────────────────────────────────────────────────────────
# 5. Create venv + pip install if needed
# ─────────────────────────────────────────────────────────────────────────────
VENV=".venv"
if [ ! -d "$VENV" ]; then
    info "Creating Python virtual environment in $VENV..."
    "$PYTHON_BIN" -m venv "$VENV"
fi

VENV_PYTHON="$VENV/bin/python"
VENV_PIP="$VENV/bin/pip"

info "Installing Python dependencies..."
"$VENV_PIP" install --upgrade pip -q
"$VENV_PIP" install -r backend/requirements.txt -q

# ─────────────────────────────────────────────────────────────────────────────
# 6. npm install if needed
# ─────────────────────────────────────────────────────────────────────────────
if [ ! -d "frontend/node_modules" ]; then
    info "Installing Node.js dependencies..."
    cd frontend && npm install --silent && cd "$SCRIPT_DIR"
else
    info "Node.js dependencies already installed — skipping npm install."
fi

# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# Kill any stale processes from a previous run
# ─────────────────────────────────────────────────────────────────────────────
FLASK_PORT="${FLASK_PORT:-8000}"
VITE_PORT="${VITE_PORT:-5173}"

_kill_port() {
    local port="$1"
    local pids
    pids=$(lsof -ti:"$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "$pids" | xargs kill -9 2>/dev/null || true
        info "Killed stale process(es) on port $port"
    fi
}

info "Clearing stale processes on ports ${FLASK_PORT} and ${VITE_PORT}..."
_kill_port "$FLASK_PORT"
_kill_port "$VITE_PORT"

# Process management — track PIDs for clean teardown
# ─────────────────────────────────────────────────────────────────────────────
FLASK_PID=""
VITE_PID=""
RQ_PID=""
REDIS_STARTED=false

FLASK_LOG="$SCRIPT_DIR/flask.log"
VITE_LOG="$SCRIPT_DIR/vite.log"
RQ_LOG="$SCRIPT_DIR/rq-worker.log"
REDIS_LOG="$SCRIPT_DIR/redis.log"

cleanup() {
    echo ""
    info "Shutting down Pravaah OS..."
    # Reverse-order shutdown: Vite → Flask → RQ worker → Redis
    [ -n "$VITE_PID" ]  && kill "$VITE_PID"  2>/dev/null && info "Vite stopped  (PID $VITE_PID)"
    [ -n "$FLASK_PID" ] && kill "$FLASK_PID" 2>/dev/null && info "Flask stopped (PID $FLASK_PID)"
    [ -n "$RQ_PID" ]    && kill "$RQ_PID"    2>/dev/null && info "RQ worker stopped (PID $RQ_PID)"
    if [ "$REDIS_STARTED" = true ]; then
        redis-cli shutdown nosave 2>/dev/null && info "Redis stopped." || true
    fi
    success "Goodbye!"
    exit 0
}
trap cleanup INT TERM

# ─────────────────────────────────────────────────────────────────────────────
# 7. Start Redis (daemonize)
# ─────────────────────────────────────────────────────────────────────────────
info "Starting Redis..."
# Check if Redis is already running
if redis-cli ping &>/dev/null 2>&1; then
    info "Redis already running — skipping start."
else
    redis-server --daemonize yes --logfile "$REDIS_LOG"
    REDIS_STARTED=true
    # Wait for Redis to be ready
    for i in $(seq 1 10); do
        if redis-cli ping &>/dev/null 2>&1; then
            success "Redis is ready."
            break
        fi
        sleep 1
        if [ "$i" -eq 10 ]; then
            error "Redis did not start within 10 seconds."
            exit 1
        fi
    done
fi

# ─────────────────────────────────────────────────────────────────────────────
# 8. Start RQ worker in background
# ─────────────────────────────────────────────────────────────────────────────
info "Starting RQ worker (queue: pravaah)..."
# OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES prevents a macOS fork() crash
# that occurs when native extensions (e.g. ChromaDB/hnswlib) are loaded
# in a thread before the work-horse process is forked.
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES PYTHONPATH="$SCRIPT_DIR" \
    "$VENV/bin/rq" worker pravaah --with-scheduler \
    > "$RQ_LOG" 2>&1 &
RQ_PID=$!
success "RQ worker started (PID $RQ_PID) — log: rq-worker.log"

# ─────────────────────────────────────────────────────────────────────────────
# 9. Start Flask in background
# ─────────────────────────────────────────────────────────────────────────────
FLASK_HOST="${FLASK_HOST:-0.0.0.0}"

info "Starting Flask on http://localhost:${FLASK_PORT} ..."
PYTHONPATH="$SCRIPT_DIR" "$VENV_PYTHON" -m backend.app \
    > "$FLASK_LOG" 2>&1 &
FLASK_PID=$!

# ─────────────────────────────────────────────────────────────────────────────
# 10. Start Vite (--strict-port so it fails if port is taken, not drifts)
# ─────────────────────────────────────────────────────────────────────────────
info "Starting Vite dev server on http://localhost:${VITE_PORT} ..."
cd frontend && npm run dev -- --port "$VITE_PORT" --strictPort > "$VITE_LOG" 2>&1 &
VITE_PID=$!
cd "$SCRIPT_DIR"

# ─────────────────────────────────────────────────────────────────────────────
# 11. Poll Flask and Vite until ready (30s timeout each)
# ─────────────────────────────────────────────────────────────────────────────
wait_for_port() {
    local name="$1"
    local port="$2"
    local max_wait=30
    local elapsed=0

    while [ $elapsed -lt $max_wait ]; do
        if command -v curl &>/dev/null; then
            if curl -s --max-time 1 "http://localhost:${port}" > /dev/null 2>&1 || \
               curl -s --max-time 1 "http://localhost:${port}/health" > /dev/null 2>&1; then
                return 0
            fi
        else
            # fallback: check if port is listening (macOS + Linux compatible)
            if (echo > /dev/tcp/localhost/"$port") 2>/dev/null; then
                return 0
            fi
        fi
        sleep 1
        elapsed=$((elapsed + 1))
        echo -ne "${CYAN}[pravaah]${NC} Waiting for ${name} (${elapsed}s)...\r"
    done
    return 1
}

if wait_for_port "Flask" "$FLASK_PORT"; then
    success "Flask is ready at http://localhost:${FLASK_PORT}"
else
    error "Flask did not start within 30 seconds."
    error "Check logs: flask.log"
    tail -20 "$FLASK_LOG" >&2
    cleanup
fi

if wait_for_port "Vite" "$VITE_PORT"; then
    success "Vite is ready at http://localhost:${VITE_PORT}"
else
    error "Vite did not start within 30 seconds."
    error "Check logs: vite.log"
    tail -20 "$VITE_LOG" >&2
    cleanup
fi

# ─────────────────────────────────────────────────────────────────────────────
# 12. Print success banner
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}┌──────────────────────────────────────┐${NC}"
echo -e "${GREEN}${BOLD}│   PRAVAAH OS v2 — RUNNING            │${NC}"
echo -e "${GREEN}${BOLD}│   App:  http://localhost:${VITE_PORT}       │${NC}"
echo -e "${GREEN}${BOLD}│   API:  http://localhost:${FLASK_PORT}       │${NC}"
echo -e "${GREEN}${BOLD}│   Redis: localhost:6379              │${NC}"
echo -e "${GREEN}${BOLD}└──────────────────────────────────────┘${NC}"
echo ""
echo -e "${CYAN}  Logs: flask.log | vite.log | rq-worker.log | redis.log${NC}"
echo -e "${CYAN}  Press Ctrl+C to stop all services${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Keep running until Ctrl+C
# ─────────────────────────────────────────────────────────────────────────────
# Monitor both processes; exit if either dies unexpectedly
while true; do
    if ! kill -0 "$FLASK_PID" 2>/dev/null; then
        error "Flask process died unexpectedly."
        error "Last 20 lines of Flask log (flask.log):"
        tail -20 "$FLASK_LOG" >&2
        cleanup
    fi
    if ! kill -0 "$VITE_PID" 2>/dev/null; then
        error "Vite process died unexpectedly."
        error "Last 20 lines of Vite log (vite.log):"
        tail -20 "$VITE_LOG" >&2
        cleanup
    fi
    if ! kill -0 "$RQ_PID" 2>/dev/null; then
        error "RQ worker process died unexpectedly."
        error "Last 20 lines of RQ log (rq-worker.log):"
        tail -20 "$RQ_LOG" >&2
        cleanup
    fi
    sleep 2
done
