#!/usr/bin/env bash
# tsk022b_apply.sh — apply TSK-022B + TSK-022C end-to-end di local dev.
#
# Steps:
#   1. git push origin main  (push 3 commits ke remote)
#   2. cd frontend && npm install  (install react-markdown + remark-gfm)
#   3. cd backend && alembic upgrade head  (apply 2 migrations baru)
#   4. (optional) restart dev servers
#
# Usage:
#   chmod +x tsk022b_apply.sh
#   ./tsk022b_apply.sh
#
# Catatan: script ini IDEMPOTENT — aman dijalankan ulang.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# ─── Pretty logging ───────────────────────────────────────────────
log() { echo -e "\033[1;34m[$(date +%H:%M:%S)] $*\033[0m"; }
ok()  { echo -e "\033[1;32m  ✓ $*\033[0m"; }
warn(){ echo -e "\033[1;33m  ⚠ $*\033[0m"; }
err() { echo -e "\033[1;31m  ✗ $*\033[0m" >&2; }

# ─── Pre-flight ────────────────────────────────────────────────────
log "Pre-flight check"
[ -d backend ] || { err "Run dari root repo (backend/ tidak ditemukan)"; exit 1; }
[ -d frontend ] || { err "frontend/ tidak ditemukan"; exit 1; }
ok "Repo structure OK"

# ─── Step 1: Git push ──────────────────────────────────────────────
log "Step 1/4 — git push origin main"
UNPUSHED=$(git rev-list HEAD ^origin/main --count 2>/dev/null || echo "0")
if [ "$UNPUSHED" -gt 0 ]; then
  echo "  → $UNPUSHED commit(s) unpushed:"
  git log --oneline origin/main..HEAD | sed 's/^/    /'
  git push origin main
  ok "Pushed $UNPUSHED commit(s)"
else
  ok "Tidak ada commit unpushed, skip"
fi

# ─── Step 2: Frontend npm install ─────────────────────────────────
log "Step 2/4 — npm install (frontend)"
cd frontend
if [ -f node_modules/.package-lock.json ] && diff -q package-lock.json node_modules/.package-lock.json >/dev/null 2>&1; then
  ok "node_modules sudah sync dengan package-lock.json"
else
  npm install
  ok "npm install selesai"
fi
cd "$REPO_ROOT"

# ─── Step 3: Backend alembic upgrade ──────────────────────────────
log "Step 3/4 — alembic upgrade head (backend)"
cd backend
if [ ! -d .venv ]; then
  err ".venv belum ada. Run: python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
  exit 1
fi

# Source venv & jalankan alembic
source .venv/bin/activate
CURRENT=$(alembic current 2>/dev/null | head -1 | awk '{print $1}' || echo "none")
echo "  → Current revision: $CURRENT"
alembic upgrade head 2>&1 | tail -15
NEW=$(alembic current 2>/dev/null | head -1 | awk '{print $1}' || echo "none")
echo "  → After upgrade: $NEW"
ok "Migration applied"
deactivate
cd "$REPO_ROOT"

# ─── Step 4: Restart dev server hint ─────────────────────────────
log "Step 4/4 — restart dev servers (manual)"
echo
echo "Jalankan di 2 terminal terpisah:"
echo
echo "  Terminal 1 (backend):"
echo "    cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000"
echo
echo "  Terminal 2 (frontend):"
echo "    cd frontend && npm run dev"
echo
echo "Atau pakai existing script: ./start.sh"
echo
ok "All deployment steps selesai. Browser ready di http://localhost:5173"
