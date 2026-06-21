#!/usr/bin/env bash
# setup.sh — One-time setup for Odysseus platform
# Creates data dirs, runs DB migrations, migrates VR video data,
# installs frontend deps, builds frontend, starts all services.
#
# Usage: ./setup.sh [--skip-services]

set -euo pipefail

ROOT_DIR="/Users/johndoe/odysseus"
LOG_DIR="$ROOT_DIR/logs"
DATA_DIR="$ROOT_DIR/data"
VIDEO_DATA_DIR="$DATA_DIR/video"
VIDEO_DB_BACKUP="/Users/johndoe/Desktop/vr video/backend/data/videos.db"

SKIP_SERVICES=false
for arg in "$@"; do
  [ "$arg" = "--skip-services" ] && SKIP_SERVICES=true
done

echo "═══════════════════════════════════════════════════"
echo "  Odysseus Platform — Setup"
echo "═══════════════════════════════════════════════════"

# ── 1. Create data directories ────────────────────────────────────
echo ""
echo "── Creating data directories ──"
mkdir -p "$DATA_DIR" "$VIDEO_DATA_DIR/thumbs" "$VIDEO_DATA_DIR/models" "$LOG_DIR"
echo "  $DATA_DIR"
echo "  $VIDEO_DATA_DIR"
echo "  $LOG_DIR"

# ── 2. Install backend Python dependencies ────────────────────────
echo ""
echo "── Installing backend Python dependencies ──"
cd "$ROOT_DIR/backend"
if [ -d "venv" ]; then
  echo "  Virtual environment already exists"
else
  echo "  Creating virtual environment..."
  python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt 2>/dev/null || pip install -q \
  fastapi uvicorn[standard] sqlalchemy[asyncio] aiosqlite \
  pydantic-settings python-jose[cryptography] passlib[bcrypt] \
  httpx python-multipart
echo "  Python dependencies installed"

# ── 3. Run database migrations (create tables) ───────────────────
echo ""
echo "── Running database migrations ──"
cd "$ROOT_DIR/backend"
python3 -c "
import asyncio
from database import init_db
asyncio.run(init_db())
print('  Database tables created')
"
echo "  Migrations complete"

# ── 4. Migrate VR video data ──────────────────────────────────────
echo ""
echo "── Migrating VR video data ──"
if [ -f "$VIDEO_DB_BACKUP" ]; then
  if [ -f "$VIDEO_DATA_DIR/videos.db" ]; then
    echo "  videos.db already exists in data dir, skipping copy"
  else
    cp "$VIDEO_DB_BACKUP" "$VIDEO_DATA_DIR/videos.db"
    echo "  Copied videos.db → $VIDEO_DATA_DIR/videos.db"
  fi
  # Count records
  COUNT=$(sqlite3 "$VIDEO_DATA_DIR/videos.db" "SELECT COUNT(*) FROM videos;" 2>/dev/null || echo "?")
  echo "  Video records: $COUNT"
else
  echo "  WARNING: No videos.db found at $VIDEO_DB_BACKUP"
  echo "  Skipping VR data migration"
fi

# ── 5. Install frontend dependencies ──────────────────────────────
echo ""
echo "── Installing frontend dependencies ──"
cd "$ROOT_DIR/frontend"
if [ -d "node_modules" ]; then
  echo "  Dependencies already installed"
else
  npm install
  echo "  Dependencies installed"
fi

# ── 6. Build frontend ─────────────────────────────────────────────
echo ""
echo "── Building frontend ──"
npm run build
echo "  Frontend built → $ROOT_DIR/frontend/dist"

# ── 7. Start services ─────────────────────────────────────────────
echo ""
if $SKIP_SERVICES; then
  echo "── Skipping service start (--skip-services) ──"
  echo ""
  echo "  To start services manually:"
  echo "    ./start.sh        # production mode"
  echo "    ./manage.sh start # dev mode (includes frontend dev server)"
else
  echo "── Starting services ──"
  cd "$ROOT_DIR"
  bash start.sh
fi

# ── Summary ───────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  Setup Complete!"
echo "═══════════════════════════════════════════════════"
echo ""
echo "  Quick reference:"
echo "    ./start.sh         — Start production (built frontend + API)"
echo "    ./stop.sh          — Stop production services"
echo "    ./manage.sh start  — Start dev mode (all services)"
echo "    ./manage.sh stop   — Stop dev services"
echo "    ./manage.sh status — Check service status"
echo ""
echo "  Launchd (start on boot):"
echo "    cp odysseus.service ~/Library/LaunchAgents/com.odysseus.platform.plist"
echo "    launchctl load ~/Library/LaunchAgents/com.odysseus.platform.plist"
echo "═══════════════════════════════════════════════════"
