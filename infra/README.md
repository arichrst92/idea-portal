# IDEA Portal — Infrastructure

Docker Compose + Nginx config untuk dev, staging, dan production.

## Services (docker-compose.yml di root)

| Service | Port | Purpose |
|---|---|---|
| `postgres` | 5432 | PostgreSQL 16 + extensions (uuid-ossp, pgcrypto, pg_trgm) |
| `redis` | 6379 | Cache + Celery broker/result backend |
| `minio` | 9000 + 9001 | S3-compatible storage (PDF slip gaji, BA, attachments) |
| `backend` | 8000 | FastAPI + Uvicorn |
| `celery-worker` | — | Background jobs (profile: `full`) |
| `frontend` | 5173 | Vite/Nginx (profile: `full`) |

## Quick Start

```bash
# Dev (backend + DB + Redis + MinIO running, frontend di host)
docker compose up -d postgres redis minio backend
cd frontend && npm run dev  # HMR lebih cepat di host

# Full stack di Docker (frontend prod build via nginx)
docker compose --profile full up -d

# Hentikan
docker compose down

# Reset semua data (HATI-HATI)
docker compose down -v
```

## MinIO Console
http://localhost:9001 (user `minio_admin` / pass `minio_dev_pass`)

Buat bucket `idea-portal` saat first run (atau biarkan backend yang init).

## PostgreSQL
```bash
docker compose exec postgres psql -U idea -d idea_portal
```

## Production Deployment

`infra/nginx/nginx.conf` adalah reverse proxy untuk production. Setup full:
1. Build images: `docker build` per service
2. Push ke container registry (GHCR/Docker Hub)
3. Deploy ke VPS (Hetzner/Contabo/GCP) dengan docker-compose.prod.yml
4. Setup Let's Encrypt via certbot
5. DNS portal.ide.asia → IP server

(Detail playbook akan ditambah di PH4 — Data Migration epic).
