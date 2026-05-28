#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# boot_local.sh — Boot IDEA Portal di localhost untuk smoke testing
#
# Yang dijalankan:
# 1. Docker compose up postgres + redis + minio
# 2. Setup backend venv + install deps (uv)
# 3. Generate alembic migration (sekali saja)
# 4. Run migration
# 5. Run seed (roles + permissions + admin user)
# 6. Start backend uvicorn (background)
# 7. Setup frontend npm install (sekali saja)
# 8. Start frontend Vite dev server (background)
#
# Output: PID file di /tmp/idea_portal/ supaya bisa stop later.
# Stop: ./stop_local.sh
# ─────────────────────────────────────────────────────────────────

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
RESET='\033[0m'

step() { echo -e "\n${BOLD}${BLUE}━━━ $* ━━━${RESET}"; }
ok()   { echo -e "${GREEN}  ✓${RESET} $*"; }
warn() { echo -e "${YELLOW}  ⚠${RESET} $*"; }
err()  { echo -e "${RED}  ✗${RESET} $*"; }

cd "$(dirname "$0")"
ROOT="$(pwd)"

# Tmp dir untuk PIDs + logs
TMP_DIR="/tmp/idea_portal"
mkdir -p "$TMP_DIR"

# ─── Preflight ──────────────────────────────────────────────────
step "Preflight checks"
command -v docker &>/dev/null && ok "docker $(docker --version | head -1)" || { err "Docker not installed"; exit 1; }
command -v uv &>/dev/null && ok "uv $(uv --version)" || { err "uv not installed (brew install uv)"; exit 1; }
command -v node &>/dev/null && ok "node $(node --version)" || { err "Node not installed"; exit 1; }
command -v npm &>/dev/null && ok "npm $(npm --version)"

# ─── Boot Docker services ───────────────────────────────────────
step "Boot docker services (postgres + redis + minio)"
docker compose up -d postgres redis minio
echo "Waiting 8 seconds untuk services boot..."
sleep 8

if docker compose ps postgres | grep -q "healthy"; then
    ok "postgres healthy"
else
    warn "postgres still starting, waiting 10 more seconds..."
    sleep 10
fi
ok "Services boot done. docker compose ps:"
docker compose ps

# ─── Backend setup ──────────────────────────────────────────────
step "Backend setup (uv venv + deps)"
cd "$ROOT/backend"

# .env (kalau belum ada)
if [ ! -f ".env" ]; then
    cp .env.example .env
    ok "Created backend/.env from .env.example"
else
    ok "backend/.env exists"
fi

# Override DATABASE_URL untuk koneksi dari host (bukan dari container)
if grep -q "@postgres:5432" .env; then
    sed -i.bak 's|@postgres:5432|@localhost:5432|g' .env
    sed -i.bak 's|redis://redis:|redis://localhost:|g' .env
    sed -i.bak 's|minio:9000|localhost:9000|g' .env
    rm .env.bak
    ok "Patched .env service hosts → localhost (untuk run uvicorn di host)"
fi

# Install deps
if [ ! -d ".venv" ]; then
    uv venv
    ok "Created .venv"
fi

uv pip install -e ".[dev]" --quiet
ok "Dependencies installed"

# ─── Migration ──────────────────────────────────────────────────
step "Database migration"
# shellcheck disable=SC1091
source .venv/bin/activate

MIGRATION_COUNT=$(find alembic/versions -name "*.py" -not -name "__*" 2>/dev/null | wc -l | tr -d ' ')
if [ "$MIGRATION_COUNT" -eq 0 ]; then
    echo "  Generating initial migration..."
    alembic revision --autogenerate -m "initial_schema_47_tables" 2>&1 | tail -10
    ok "Migration generated"
else
    ok "Migration exists ($MIGRATION_COUNT files)"
fi

echo "  Applying migrations..."
alembic upgrade head 2>&1 | tail -5
ok "Migration applied"

# ─── Seed ───────────────────────────────────────────────────────
step "Seed (roles + permissions + admin)"
python -m app.seed
ok "Seed done"

# ─── Start backend ──────────────────────────────────────────────
step "Start backend (uvicorn)"

# Kill existing backend kalau ada
if [ -f "$TMP_DIR/backend.pid" ]; then
    OLD_PID=$(cat "$TMP_DIR/backend.pid")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        warn "Killing old backend PID $OLD_PID"
        kill "$OLD_PID" 2>/dev/null || true
        sleep 2
    fi
fi

# Start uvicorn in background
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload \
    > "$TMP_DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$TMP_DIR/backend.pid"
ok "Backend started (PID $BACKEND_PID, log: $TMP_DIR/backend.log)"

# Wait for backend ready
echo "  Waiting backend ready..."
for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
        ok "Backend healthy: http://localhost:8000"
        break
    fi
    sleep 1
done

if ! curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    err "Backend not responding setelah 10 detik. Cek log: tail -50 $TMP_DIR/backend.log"
    exit 1
fi

# ─── Frontend setup ─────────────────────────────────────────────
step "Frontend setup (npm install)"
cd "$ROOT/frontend"

if [ ! -f ".env" ]; then
    cp .env.example .env
    ok "Created frontend/.env"
fi

if [ ! -d "node_modules" ]; then
    npm install 2>&1 | tail -3
    ok "npm install done"
else
    ok "node_modules exists"
fi

# ─── Start frontend ─────────────────────────────────────────────
step "Start frontend (Vite dev)"

if [ -f "$TMP_DIR/frontend.pid" ]; then
    OLD_PID=$(cat "$TMP_DIR/frontend.pid")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        warn "Killing old frontend PID $OLD_PID"
        kill "$OLD_PID" 2>/dev/null || true
        sleep 2
    fi
fi

nohup npm run dev > "$TMP_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$TMP_DIR/frontend.pid"
ok "Frontend started (PID $FRONTEND_PID, log: $TMP_DIR/frontend.log)"

# Wait for Vite
echo "  Waiting Vite ready..."
for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -fsS http://localhost:5173 >/dev/null 2>&1; then
        ok "Frontend live: http://localhost:5173"
        break
    fi
    sleep 1
done

# ─── Summary ────────────────────────────────────────────────────
step "🎉 IDEA Portal live di localhost!"
echo ""
echo -e "${GREEN}${BOLD}URLs:${RESET}"
echo "  Frontend:     http://localhost:5173"
echo "  Backend API:  http://localhost:8000"
echo "  API docs:     http://localhost:8000/docs"
echo "  MinIO UI:     http://localhost:9001 (minio_admin / minio_dev_pass)"
echo ""
echo -e "${GREEN}${BOLD}Test login:${RESET}"
echo "  NIK:       ADMIN-001"
echo "  Password:  admin123"
echo ""
echo -e "${YELLOW}${BOLD}Logs:${RESET}"
echo "  Backend:   tail -f $TMP_DIR/backend.log"
echo "  Frontend:  tail -f $TMP_DIR/frontend.log"
echo "  Docker:    docker compose logs -f"
echo ""
echo -e "${YELLOW}${BOLD}Stop:${RESET}"
echo "  ./stop_local.sh"
echo ""
echo -e "${BLUE}${BOLD}Smoke test:${RESET}"
echo "  Lihat SMOKE_TEST_GUIDE.md untuk checklist lengkap."
echo ""
echo "  Quick browser test:"
echo "    open http://localhost:5173"
