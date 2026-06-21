#!/usr/bin/env bash
# stop.sh — Stop all Odysseus platform services
# Graceful SIGTERM → SIGKILL, cleans up PID files
#
# Usage: ./stop.sh

set -euo pipefail

PID_DIR="/tmp/odysseus-services"

SERVICES=("odysseus-backend" "ai-gateway")

echo "═══════════════════════════════════════════"
echo "  Odysseus Platform — Stop"
echo "═══════════════════════════════════════════"

for name in "${SERVICES[@]}"; do
  pf="$PID_DIR/$name.pid"
  if [ -f "$pf" ]; then
    pid=$(cat "$pf" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      echo "  Stopping $name (PID $pid)..."
      # Graceful
      kill -TERM "$pid" 2>/dev/null || true
      i=0
      while [ $i -lt 5 ] && kill -0 "$pid" 2>/dev/null; do
        sleep 1
        i=$((i+1))
      done
      # Force
      if kill -0 "$pid" 2>/dev/null; then
        echo "  Force-killing $name (PID $pid)..."
        kill -9 "$pid" 2>/dev/null || true
        sleep 1
      fi
      echo "  $name stopped"
    else
      echo "  $name not running (stale PID file)"
    fi
    rm -f "$pf"
  else
    echo "  $name not running (no PID file)"
  fi
done

# Clean up any remaining PID files
rm -f "$PID_DIR"/*.pid 2>/dev/null || true

echo ""
echo "  All Odysseus services stopped."
echo "═══════════════════════════════════════════"
