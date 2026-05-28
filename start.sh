#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# start.sh — Single command untuk run IDEA Portal di localhost
#
# Usage:
#   ./start.sh           # Start docker + backend + frontend, show live logs
#   ./start.sh stop      # Stop semua
#   ./start.sh logs      # Tail logs (kalau jalan di background)
#   ./start.sh restart   # Stop + start
#
# Ctrl+C untuk stop graceful.
# ─────────────────────────────────────────────────────────────────

set -uo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# Paths
cd "$(dirname "$0")"
ROOT="$(pwd)"
TMP_DIR="/tmp/idea_portal"
mkdir -p "$TMP_DIR"

# ─── Helpers ────────────────────────────────────────────────────
banner() {
    echo ""
    echo -e "${BOLD}${BLUE}╔══════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${BOLD}${BLUE}║  $1${RESET}"
    echo -e "${BOLD}${BLUE}╚══════════════════════════════════════════════════════════╝${RESET}"
}

step() { echo -e "\n${BOLD}${BLUE}━━━ $* ━━━${RESET}"; }
ok()   { echo -e "${GREEN}  ✓${RESET} $*"; }
warn() { echo -e "${YELLOW}  ⚠${RESET} $*"; }
err()  { echo -e "${RED}  ✗${RESET} $*"; }

# ─── Stop ──────────────────────────────────────────────────────
stop_all() {
    step "Stopping services"

    # Stop backend
    if [ -f "$TMP_DIR/backend.pid" ]; then
        PID=$(cat "$TMP_DIR/backend.pid")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null && ok "Backend stopped (PID $PID)"
        fi
        rm -f "$TMP_DIR/backend.pid"
    fi

    # Stop frontend
    if [ -f "$TMP_DIR/frontend.pid" ]; then
        PID=$(cat "$TMP_DIR/frontend.pid")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID" 2>/dev/null && ok "Frontend stopped (PID $PID)"
        fi
        rm -f "$TMP_DIR/frontend.pid"
    fi

    # Cleanup orphan processes di port 8000 + 5173
    lsof -ti :8000 2>/dev/null | xargs kill -9 2>/dev/null || true
    lsof -ti :5173 2>/dev/null | xargs kill -9 2>/dev/null || true

    # Stop docker (data preserved)
    docker compose stop postgres redis minio 2>/dev/null && ok "Docker services stopped" || warn "Docker already stopped"
}

# ─── Logs ──────────────────────────────────────────────────────
tail_logs() {
    step "Tailing logs (Ctrl+C untuk stop tail, services tetap jalan)"
    echo -e "${CYAN}[BACKEND]${RESET} $TMP_DIR/backend.log"
    echo -e "${PURPLE}[FRONTEND]${RESET} $TMP_DIR/frontend.log"
    echo ""

    # Prefix each line with colored tag
    (tail -F "$TMP_DIR/backend.log" 2>/dev/null | sed -u "s|^|$(printf '%b' "${CYAN}[BACKEND]${RESET} ")|") &
    BACKEND_TAIL=$!
    (tail -F "$TMP_DIR/frontend.log" 2>/dev/null | sed -u "s|^|$(printf '%b' "${PURPLE}[FRONTEND]${RESET} ")|") &
    FRONTEND_TAIL=$!

    trap "kill $BACKEND_TAIL $FRONTEND_TAIL 2>/dev/null; exit 0" INT TERM
    wait
}

# ─── Argument handler ──────────────────────────────────────────
case "${1:-start}" in
    stop)
        stop_all
        exit 0
        ;;
    logs)
        tail_logs
        exit 0
        ;;
    restart)
        stop_all
        sleep 2
        ;;
    start|"")
        # Lanjut ke start flow
        ;;
    *)
        echo "Usage: $0 [start|stop|logs|restart]"
        exit 1
        ;;
esac

banner "🚀 IDEA Portal — Starting localhost stack"

# ─── 1. Docker services ────────────────────────────────────────
step "Boot Docker services (postgres + redis + minio)"
docker compose up -d postgres redis minio
sleep 5

if docker compose ps postgres 2>/dev/null | grep -q "healthy"; then
    ok "Postgres healthy"
else
    warn "Postgres still starting, waiting..."
    sleep 8
fi
ok "Docker services up"

# ─── 2. Backend ────────────────────────────────────────────────
step "Start backend (FastAPI uvicorn)"

# Stop existing
if [ -f "$TMP_DIR/backend.pid" ]; then
    OLD=$(cat "$TMP_DIR/backend.pid")
    kill "$OLD" 2>/dev/null && warn "Killed old backend PID $OLD"
fi
lsof -ti :8000 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

# Verify venv
if [ ! -d "backend/.venv" ]; then
    err "backend/.venv tidak ada. Run: cd backend && uv venv && uv pip install -e \".[dev]\""
    exit 1
fi

# Start backend in background
cd "$ROOT/backend"
nohup ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload \
    > "$TMP_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$TMP_DIR/backend.pid"
cd "$ROOT"

# Wait for ready
echo "  Waiting backend ready..."
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
    if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
        ok "Backend healthy: http://localhost:8000 (PID $BACKEND_PID)"
        break
    fi
    sleep 1
done
if ! curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    err "Backend tidak respond. Cek log: tail -50 $TMP_DIR/backend.log"
    tail -30 "$TMP_DIR/backend.log"
    exit 1
fi

# ─── 3. Frontend ───────────────────────────────────────────────
step "Start frontend (Vite dev)"

if [ -f "$TMP_DIR/frontend.pid" ]; then
    OLD=$(cat "$TMP_DIR/frontend.pid")
    kill "$OLD" 2>/dev/null && warn "Killed old frontend PID $OLD"
fi
lsof -ti :5173 2>/dev/null | xargs kill -9 2>/dev/null || true
sleep 1

if [ ! -d "frontend/node_modules" ]; then
    warn "frontend/node_modules tidak ada, install dulu..."
    cd "$ROOT/frontend" && npm install 2>&1 | tail -3
    cd "$ROOT"
fi

cd "$ROOT/frontend"
nohup npm run dev > "$TMP_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$TMP_DIR/frontend.pid"
cd "$ROOT"

echo "  Waiting Vite ready..."
for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -fsS http://localhost:5173 >/dev/null 2>&1; then
        ok "Frontend live: http://localhost:5173 (PID $FRONTEND_PID)"
        break
    fi
    sleep 1
done

# ─── Summary ───────────────────────────────────────────────────
banner "🎉 IDEA Portal live di localhost"

cat <<EOF

${BOLD}${GREEN}URLs:${RESET}
  Frontend:     ${CYAN}http://localhost:5173${RESET}
  Backend API:  ${CYAN}http://localhost:8000${RESET}
  API docs:     ${CYAN}http://localhost:8000/docs${RESET}
  MinIO UI:     ${CYAN}http://localhost:9001${RESET} (minio_admin / minio_dev_pass)

${BOLD}${GREEN}Test login:${RESET}
  NIK:       ${YELLOW}ADMIN-001${RESET}
  Password:  ${YELLOW}admin123${RESET}

${BOLD}${YELLOW}Commands:${RESET}
  ${CYAN}./start.sh logs${RESET}      — tail live logs (backend + frontend)
  ${CYAN}./start.sh stop${RESET}      — stop semua services
  ${CYAN}./start.sh restart${RESET}   — stop + start ulang

${BOLD}Tip:${RESET} Run ${CYAN}./start.sh logs${RESET} di tab terminal lain untuk lihat
live logs sambil kerja di terminal utama.

EOF

# Auto-tail kalau sudah running OK
read -t 3 -p "Tail logs sekarang? (y/N, default N dalam 3 detik): " confirm || true
echo ""
if [ "${confirm:-}" = "y" ]; then
    tail_logs
fi
