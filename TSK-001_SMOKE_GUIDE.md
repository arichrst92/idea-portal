# TSK-001 — Manual Smoke Test Guide

Quick verification setelah TSK-001 implementasi. Jalankan di Mac local.

## Prerequisites

```bash
# Docker Desktop running
docker ps  # harus respond, tidak error

# uv + Python 3.12 installed
uv --version
python3.12 --version
```

## 1. Setup Database & Migration

```bash
cd ~/Projects/idea-portal

# Boot infra services
docker compose up -d postgres redis minio

# Tunggu postgres healthy (~10 detik)
docker compose ps

# Setup backend env + deps
cd backend
cp .env.example .env
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Generate initial migration dari 49 models
alembic revision --autogenerate -m "initial_schema_47_tables"

# Verify migration looks sensible (49 CREATE TABLE statements)
ls -la alembic/versions/
cat alembic/versions/*_initial_schema*.py | head -50

# Apply migration
alembic upgrade head

# Verify tables exist
docker compose exec postgres psql -U idea -d idea_portal -c "\dt" | head -60
# Expected: ~49 tables across all domains
```

## 2. Seed Initial Data

```bash
# Insert roles + admin user
uv run python -m app.seed

# Expected output:
# ━━━ IDEA Portal — Database Seed ━━━
# Seeding roles...
#   + Role: DIREKTUR_UTAMA                  (level 1)
#   + Role: WAKIL_DIREKTUR_UTAMA            (level 11)
#   + Role: C_LEVEL                          (level 2)
#   + Role: GM                               (level 3)
#   + Role: MANAGER                          (level 4)
#   + Role: LEAD                             (level 5)
#   + Role: STAFF                            (level 6)
# Seeding admin user...
#   + User: ADMIN-001 | password: admin123 | role: DIREKTUR_UTAMA
# ✓ Seed complete.
```

## 3. Boot Backend

```bash
# Boot FastAPI (terminal 1)
cd ~/Projects/idea-portal
docker compose up backend
# OR di host: uvicorn app.main:app --reload --port 8000

# Verify health
curl http://localhost:8000/health
# {"status":"ok"}
```

## 4. Test Login API (curl)

### 4a. Happy path

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"nik":"ADMIN-001","password":"admin123"}'
```

Expected response (200):
```json
{
  "access_token": "placeholder-token-for-ADMIN-001-replace-in-tsk-002",
  "token_type": "bearer",
  "user": {
    "id": "...",
    "nik": "ADMIN-001",
    "email": "admin@ide.asia",
    "is_active": true,
    "last_login_at": "2026-05-27T...",
    "roles": [{"code": "DIREKTUR_UTAMA", "name": "Direktur Utama", "level": 1}]
  }
}
```

### 4b. Invalid NIK

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"nik":"NONEXISTENT","password":"any"}'
```

Expected (401):
```json
{"detail":{"code":"INVALID_CREDENTIALS","message":"NIK atau password tidak valid. Silakan coba lagi."}}
```

### 4c. Validation error

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"nik":"","password":""}'
```

Expected (422): Pydantic validation error with field details.

## 5. Boot Frontend

```bash
# Terminal 2
cd ~/Projects/idea-portal/frontend
cp .env.example .env
npm install
npm run dev
```

Browse: http://localhost:5173 — akan auto-redirect ke `/login`.

## 6. Test Login UI

1. Buka `http://localhost:5173/login`
2. **Test empty submit:** Click "Masuk" tanpa fill — error muncul "NIK tidak boleh kosong" + "Password tidak boleh kosong"
3. **Test invalid:** NIK = `WRONG`, password = `wrong` — Alert merah muncul dengan message dari backend
4. **Test happy:** NIK = `ADMIN-001`, password = `admin123` — redirect ke `/` (App.tsx)
5. **Test logout:** Klik "Logout" di kanan atas — kembali ke `/login`
6. **Test persisted session:** Login lagi, refresh browser (Cmd+R) — masih authenticated (Zustand persist)

## 7. Run Backend Tests

```bash
cd ~/Projects/idea-portal/backend
uv run pytest tests/test_auth.py -v
```

Expected: 7 tests passed
- test_login_success
- test_login_invalid_nik
- test_login_invalid_password
- test_login_inactive_account
- test_login_validation_empty_nik
- test_login_validation_missing_password
- test_login_locked_account_after_5_failed_attempts

## ⚠️ Known Limitations TSK-001

Berikut PR future TSK akan address:
- ❌ access_token bukan JWT real — TSK-002 akan replace
- ❌ Belum ada refresh token endpoint — TSK-002
- ❌ Belum ada RBAC enforcement di endpoint lain — TSK-003
- ❌ Belum ada audit log writer (model ready) — TSK-005
- ❌ Belum ada change password flow — TSK-007
- ❌ Belum ada mobile responsive layout — TSK-009

Status `❌` adalah expected. Goal TSK-001 = login flow E2E working dengan placeholder token.
