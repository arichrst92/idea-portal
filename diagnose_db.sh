#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# diagnose_db.sh — Identifikasi & fix masalah koneksi DB
#
# Cek:
# 1. Apa yang listening di port 5432 (Docker atau bukan)
# 2. Status Docker postgres container
# 3. Direct connection test via psycopg dari host
# 4. Kalau ada port collision → otomatis switch Docker ke 5433
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
info() { echo "    $*"; }

cd "$(dirname "$0")"

# ─── 1. Cek port 5432 ───────────────────────────────────────────
step "1. Apa yang listening di port 5432?"
PORT_OUTPUT=$(lsof -i :5432 -sTCP:LISTEN 2>/dev/null || true)
if [ -z "$PORT_OUTPUT" ]; then
    warn "Tidak ada yang listening di port 5432"
    NO_LISTENER=true
else
    echo "$PORT_OUTPUT"
    NO_LISTENER=false
    # Cek apakah owner = docker (com.docker.backend atau vpnkit)
    if echo "$PORT_OUTPUT" | grep -qE "com\.docker|vpnkit|docker-proxy"; then
        ok "Port 5432 dikuasai oleh Docker"
        DOCKER_OWNS=true
    else
        err "Port 5432 dikuasai oleh proses NON-Docker (postgres lain di host)"
        DOCKER_OWNS=false
    fi
fi

# ─── 2. Docker postgres status ──────────────────────────────────
step "2. Docker postgres container status"
DC_STATUS=$(docker compose ps postgres --format json 2>/dev/null || echo "")
if [ -z "$DC_STATUS" ]; then
    err "Docker postgres container tidak ada / tidak running"
    exit 1
else
    HEALTH=$(echo "$DC_STATUS" | python3 -c "import sys, json; d=json.loads(sys.stdin.read()); print(d.get('Health', 'unknown'))" 2>/dev/null || echo "unknown")
    STATE=$(echo "$DC_STATUS" | python3 -c "import sys, json; d=json.loads(sys.stdin.read()); print(d.get('State', 'unknown'))" 2>/dev/null || echo "unknown")
    ok "State: $STATE, Health: $HEALTH"
fi

# ─── 3. Cek DB di dalam container ───────────────────────────────
step "3. Cek database idea_portal di dalam container"
if docker compose exec -T postgres psql -U idea -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='idea_portal';" 2>/dev/null | grep -q 1; then
    ok "Database 'idea_portal' EXISTS di dalam container"
    DB_IN_CONTAINER=true
else
    warn "Database 'idea_portal' TIDAK ada di container. Akan dibuat..."
    docker compose exec -T postgres psql -U idea -d postgres -c "CREATE DATABASE idea_portal;" 2>&1 | tail -3
    DB_IN_CONTAINER=true
fi

# ─── 4. Direct connection test dari host ────────────────────────
step "4. Direct connection test dari host (psycopg)"
cd backend
source .venv/bin/activate

CONN_RESULT=$(python3 - <<'PY' 2>&1
import psycopg
import sys
try:
    conn = psycopg.connect(
        'postgresql://idea:idea_dev_pass@localhost:5432/idea_portal',
        connect_timeout=5
    )
    cur = conn.cursor()
    cur.execute("SELECT current_database(), inet_server_addr(), inet_server_port();")
    row = cur.fetchone()
    print(f"OK|db={row[0]}|addr={row[1]}|port={row[2]}")
    conn.close()
except Exception as e:
    print(f"FAIL|{type(e).__name__}|{str(e)[:300]}")
    sys.exit(1)
PY
)

if echo "$CONN_RESULT" | grep -q "^OK"; then
    ok "Direct connect SUKSES: $CONN_RESULT"
    HOST_CAN_CONNECT=true
else
    err "Direct connect GAGAL: $CONN_RESULT"
    HOST_CAN_CONNECT=false
fi

cd ..

# ─── 5. Diagnosis & saran fix ───────────────────────────────────
step "5. Diagnosis & rekomendasi"

if [ "$HOST_CAN_CONNECT" = true ]; then
    ok "Koneksi DB dari host BERHASIL — alembic seharusnya bisa jalan"
    echo ""
    info "Cobalah jalankan boot lagi:"
    info "  ./boot_local.sh"
elif [ "$NO_LISTENER" = true ]; then
    err "Tidak ada postgres listening — Docker mungkin belum boot atau crash"
    echo ""
    info "Run:"
    info "  docker compose down"
    info "  docker compose up -d postgres"
    info "  sleep 10"
    info "  ./diagnose_db.sh"
elif [ "$DOCKER_OWNS" = false ]; then
    err "POSTGRES LAIN (non-Docker) shadow port 5432"
    echo ""
    info "Solusi: switch Docker ke port 5433 supaya tidak bentrok"
    info ""
    read -p "Auto-switch Docker postgres ke port 5433? (y/N): " confirm
    if [ "$confirm" = "y" ]; then
        # Patch docker-compose.yml
        sed -i.bak 's|"5432:5432"|"5433:5432"|' docker-compose.yml
        ok "docker-compose.yml updated: 5433:5432"

        # Patch backend/.env
        sed -i.bak 's|@localhost:5432|@localhost:5433|g' backend/.env
        ok "backend/.env updated: localhost:5433"

        rm -f docker-compose.yml.bak backend/.env.bak

        # Restart postgres
        docker compose down postgres
        docker compose up -d postgres
        ok "Postgres restarted di port 5433"
        sleep 8

        info "Sekarang run: ./boot_local.sh"
    fi
else
    err "Edge case — postgres docker ada, port 5432 OK, tapi connect gagal"
    info "Cek log: docker compose logs postgres | tail -50"
fi

echo ""
