#!/bin/bash
# Stop IDEA Portal localhost stack.

set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RESET='\033[0m'

TMP_DIR="/tmp/idea_portal"

step() { echo -e "\n${BOLD}━━━ $* ━━━${RESET}"; }
ok()   { echo -e "${GREEN}  ✓${RESET} $*"; }
warn() { echo -e "${YELLOW}  ⚠${RESET} $*"; }

cd "$(dirname "$0")"

step "Stop frontend"
if [ -f "$TMP_DIR/frontend.pid" ]; then
    PID=$(cat "$TMP_DIR/frontend.pid")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" && ok "Frontend stopped (PID $PID)"
    else
        warn "Frontend PID $PID not running"
    fi
    rm -f "$TMP_DIR/frontend.pid"
else
    warn "No frontend PID file"
fi

step "Stop backend"
if [ -f "$TMP_DIR/backend.pid" ]; then
    PID=$(cat "$TMP_DIR/backend.pid")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID" && ok "Backend stopped (PID $PID)"
    else
        warn "Backend PID $PID not running"
    fi
    rm -f "$TMP_DIR/backend.pid"
else
    warn "No backend PID file"
fi

step "Stop docker services"
docker compose stop postgres redis minio
ok "Docker services stopped (data preserved)"

echo ""
echo -e "${GREEN}Done.${RESET} Run ./boot_local.sh untuk start lagi."
echo "Untuk reset semua data: docker compose down -v"
