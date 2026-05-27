# IDEA Portal — Backend

FastAPI + PostgreSQL 16 + Celery + Redis + MinIO.

## Quick Start (lokal dev)

```bash
# Pakai docker-compose dari root project (recommended)
cd ..
docker compose up backend

# ATAU manual (butuh PostgreSQL/Redis/MinIO running)
cd backend
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env  # edit .env sesuai lokal
uvicorn app.main:app --reload --port 8000
```

Browse: http://localhost:8000/docs (Swagger UI)

## Struktur Domain-Driven

```
app/
├── main.py              # FastAPI entry + lifespan
├── config.py            # Settings via pydantic
├── database.py          # SQLAlchemy 2.0 async engine
├── core/                # Shared utilities (security, deps)
├── identity/            # EP-01 — Auth, RBAC, Wakil Direktur
├── organization/        # EP-02 — Employee, Org tree
├── payroll/             # EP-05 — Payroll calc engine
├── project/             # EP-07 — Project mgmt
├── assessment/          # EP-08 — OKR + Weighted scoring
├── finance/             # EP-09 — CoA, Transaksi
├── outsource/           # EP-10 — Outsource lifecycle
├── sales/               # EP-14 — Sales funnel
└── notification/        # EP-06 — In-app notif
```

Setiap domain berisi: `models.py` + `schemas.py` + `service.py` + `router.py`.

## Konvensi

- **Style:** ruff (format + lint) — `ruff check . && ruff format .`
- **Type hints:** wajib di semua function signatures
- **Async:** semua I/O code pakai `async/await`
- **SQLAlchemy:** versi 2.0 syntax (no legacy ORM)
- **Tests:** pytest, target coverage ≥80%

## Database Migrations

```bash
# Generate migration baru (autogenerate dari model changes)
alembic revision --autogenerate -m "add users table"

# Apply migrations
alembic upgrade head

# Rollback 1 step
alembic downgrade -1
```

## Run Tests

```bash
pytest                      # All
pytest tests/unit           # Unit only
pytest -k "test_health"     # By name
pytest --cov-report=html    # HTML coverage
```

## Commit Convention

Per `CLAUDE.md` root project:
```
feat(EP-01): implement JWT auth  [TSK-002]
fix(EP-05): correct PPh21 calc   [TSK-048]
```

## Status

- ✅ Sprint 0: Skeleton siap (health endpoint, lifespan, config, security stubs)
- 🚧 Sprint 1 (PH1 M1.1): EP-01 Auth & RBAC (8 Jun 2026)
