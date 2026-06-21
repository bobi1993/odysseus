#!/usr/bin/env bash
# start.sh — Production start for Odysseus platform
# Builds frontend, starts FastAPI backend (4 workers) + AI Gateway
# All services run under nohup with PID tracking
#
# Usage: ./start.sh

set -euo pipefail

ROOT_DIR="/Users/johndoe/odysseus"
LOG_DIR="$ROOT_DIR/logs"
PID_DIR="/tmp/odysseus-services"
FRONTEND_DIST="$ROOT_DIR/frontend/dist"

mkdir -p "$LOG_DIR" "$PID_DIR"

# ── Helper: check if a PID is alive ────────────────────────────────
is_running() {
  local pf="$1"
  if [ -f "$pf" ]; then
    local pid; pid=$(cat "$pf" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
  fi
  return 1
}

echo "═══════════════════════════════════════════"
echo "  Odysseus Platform — Production Start"
echo "═══════════════════════════════════════════"

# ── 1. Build frontend ─────────────────────────────────────────────
echo ""
echo "── Building Vue 3 frontend ──"
cd "$ROOT_DIR/frontend"
if [ -d "node_modules" ]; then
  echo "  Dependencies already installed"
else
  echo "  Installing frontend dependencies..."
  npm install
fi
npm run build
echo "  Frontend built → $FRONTEND_DIST"

# ── 2. Start FastAPI backend ──────────────────────────────────────
echo ""
echo "── Starting FastAPI backend (port 7000, 4 workers) ──"
BACKEND_PID="$PID_DIR/odysseus-backend.pid"
if is_running "$BACKEND_PID"; then
  echo "  Already running (PID $(cat "$BACKEND_PID"))"
else
  cd "$ROOT_DIR/backend"
  nohup bash -c "exec uvicorn main:app --host 127.0.0.1 --port 7000 --workers 4" \
    > "$LOG_DIR/backend.log" 2>&1 &
  echo $! > "$BACKEND_PID"
  echo "  Started (PID $(cat "$BACKEND_PID"))"
fi

# ── 3. Start AI Gateway ───────────────────────────────────────────
echo ""
echo "── Starting AI Gateway (port 3005) ──"
GATEWAY_PID="$PID_DIR/ai-gateway.pid"
if is_running "$GATEWAY_PID"; then
  echo "  Already running (PID $(cat "$GATEWAY_PID"))"
else
  cd "$ROOT_DIR"
  nohup bash -c "exec node --env-file=.env.local ai-gateway.mjs" \
    > "$LOG_DIR/ai-gateway.log" 2>&1 &
  echo $! > "$GATEWAY_PID"
  echo "  Started (PID $(cat "$GATEWAY_PID"))"
fi

# ── 4. Wait for services ──────────────────────────────────────────
echo ""
echo "── Waiting for services to come up ──"
for port in 7000 3005; do
  i=0
  while [ $i -lt 15 ]; do
    if lsof -ti :"$port" 2>/dev/null | grep -q .; then
      echo "  Port $port ✓"
      break
    fi
    sleep 1
    i=$((i+1))
  done
  if [ $i -ge 15 ]; then
    echo "  Port $port ✗ (not responding after 15s)"
  fi
done

# ── Summary ───────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════"
echo "  Odysseus Platform — Running"
echo "═══════════════════════════════════════════"
echo ""
echo "  Frontend + API:  http://localhost:7000"
echo "  API docs:        http://localhost:7000/api/docs"
echo "  AI Gateway:      http://localhost:3005"
echo "  Logs:            $LOG_DIR/"
echo "  PIDs:            $PID_DIR/"
echo ""
echo "  Stop:  ./stop.sh"
echo "═══════════════════════════════════════════"
