# IDEA Internal Portal

**PT. Solusi Inovasi Bangsa (IDE Asia)**
ERP + HRIS greenfield untuk 50–200 karyawan internal · web-based, desktop-first
URL produksi: `portal.ide.asia`

---

## Status

🎉 **Design phase: 100% complete** (2026-05-26)
🏗️ **Development phase: kickoff 1 Juni 2026**

| Aspek | Status |
|---|---|
| Knowledge base (spec) | ✅ 21 section di `knowledge.md` |
| User stories | ✅ 46 stories di `IDEA_User_Stories.docx` |
| Negative cases | ✅ 45 grup / ~216 cases di `IDEA_Negative_Cases.docx` |
| Task backlog | ✅ 200 task aktif di `IDEA_Task_Management.xlsx` |
| UI mockups | ✅ 37 halaman fitur di `GUI html/` |
| Development roadmap | ✅ `IDEA_Development_Roadmap.md` |

---

## Quick Start

### Prerequisites
- **Docker Desktop** (untuk semua services)
- **Python 3.12+** + [uv](https://github.com/astral-sh/uv) (backend dev)
- **Node.js 22+** (frontend dev)
- **Git** dengan SSH key ter-link ke GitHub

### Setup pertama (5 menit)

```bash
# Clone repo
git clone git@github.com:arichrst92/idea-portal.git
cd idea-portal

# Setup env files
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
cp .env.example .env

# Boot infra + backend
docker compose up -d postgres redis minio backend

# Verifikasi backend
curl http://localhost:8000/health
# Expected: {"status":"ok"}

# Run frontend (HMR di host = lebih cepat dari Docker)
cd frontend && npm install && npm run dev
```

Browse:
- Frontend: http://localhost:5173
- API docs: http://localhost:8000/docs
- MinIO Console: http://localhost:9001 (`minio_admin` / `minio_dev_pass`)

### Buka dokumen kunci

```bash
open knowledge.md                       # Spec & aturan bisnis (21 section)
open IDEA_Development_Roadmap.md        # Timeline 14 bulan
open IDEA_Task_Management.xlsx          # Backlog 200 task
open "GUI html/IDEA_Login.html"         # Visual reference
```

---

## Struktur Repo

```
idea-portal/
├── README.md                        # ← Anda di sini
├── CLAUDE.md                        # Instruksi untuk Claude sessions
├── knowledge.md                     # Master spec (21 section)
├── IDEA_Development_Roadmap.md      # Timeline 14 bulan + 12 milestone
├── IDEA_Task_Management.xlsx        # 200 task / 25 epic / 4 phase
├── IDEA_User_Stories.docx           # 46 user stories dengan AC
├── IDEA_Negative_Cases.docx         # 45 NC grup / ~216 cases
├── GUI html/                        # 37 UI mockup HTML
│   ├── IDEA_Login.html
│   └── ... (36 file lain)
├── backend/                         # FastAPI (Python 3.12 + uv)
│   ├── app/                         # Domain-driven structure
│   │   ├── identity/                # EP-01 Auth
│   │   ├── organization/            # EP-02 Employee
│   │   ├── payroll/                 # EP-05 Payroll
│   │   └── ...
│   ├── alembic/                     # DB migrations
│   ├── tests/                       # pytest
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/                        # Vite + React 18 + TS + AntD
│   ├── src/
│   │   ├── api/                     # axios + interceptors
│   │   ├── features/                # Feature-based modules
│   │   ├── store/                   # Zustand
│   │   └── ...
│   ├── Dockerfile
│   └── package.json
├── infra/                           # Docker, nginx config
│   ├── nginx/nginx.conf
│   └── init-scripts/01-extensions.sql
├── docker-compose.yml               # Dev environment
├── .github/                         # PR template, issue templates, CI
└── .gitignore
```

---

## Tech Stack

| Layer | Teknologi |
|---|---|
| Frontend | React + TypeScript · Ant Design · Zustand + React Query |
| Backend | FastAPI (Python) · Celery + Redis |
| Database | PostgreSQL 16 · SQLAlchemy 2.0 + Alembic |
| Storage | MinIO (self-hosted S3) |
| PDF | WeasyPrint + Jinja2 |
| AI | Claude API (claude-sonnet-4-20250514) |
| Infra | Docker Compose · Nginx · Let's Encrypt |
| Monitoring | Prometheus + Grafana |

Detail lengkap di `knowledge.md` sec.16.

---

## Development Team

| Role | Pengisi |
|---|---|
| Product Owner / Tech Lead / Developer | **Ari Christian** (arichrst@ide.asia) |
| AI Pair Programmer | **Claude** (Anthropic) |

Solo dev setup dengan AI assistant. Setiap perubahan code wajib di-push ke `git@github.com:arichrst92/idea-portal.git`.

---

## Roadmap Highlights

```
Kickoff   ▌ 1 Jun 2026
PH1 ▌  8 Jun – 27 Sep 2026  · Foundation (Auth, RBAC, Master Data, Payroll)
PH2 ▌ 28 Sep – 17 Jan 2027  · Core Ops (PM, Assessment, Finance, Outsource)
PH3 ▌ 18 Jan – 11 Apr 2027  · Growth (Sales, SP, Executive Portal)
PH4 ▌ 12 Apr – 6 Jun 2027   · Intelligence (AI, Digital Sig, Analytics)
UAT ▌  7 Jun – 4 Jul 2027   · Bugfix + Training
🚀  ▌  5 Jul 2027            · GO-LIVE
```

**Target velocity:** 25–35 pts/sprint (solo + AI). Total 1.190 pts → ~36 sprint (2-minggu) → ~14 bulan. Detail lengkap di `IDEA_Development_Roadmap.md`.

---

## Git Workflow

**Branch convention:**
- `main` — production-ready code
- `feature/EP-XX-description` — fitur baru per epic
- `fix/TSK-XXX-description` — bug fix per task ID

**Commit convention** (Conventional Commits):
```
feat(EP-01): implement JWT auth with refresh token  [TSK-002]
fix(EP-05): correct PPh21 calc for variable income  [TSK-048]
docs: update knowledge.md sec 7 commission rule
chore: bump deps
```

**Push wajib** setiap milestone task selesai. Detail di `CLAUDE.md`.

---

## Kontak & Links

- **Repo:** [github.com/arichrst92/idea-portal](https://github.com/arichrst92/idea-portal)
- **Portal produksi (future):** [portal.ide.asia](https://portal.ide.asia)
- **Owner:** Ari Christian — arichrst@ide.asia
- **Company:** PT. Solusi Inovasi Bangsa (IDE Asia)
