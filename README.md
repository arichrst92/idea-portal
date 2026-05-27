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

```bash
# Clone repo
git clone git@github.com:arichrst92/idea-portal.git
cd idea-portal

# Buka dokumen kunci
open knowledge.md                       # Spec & aturan bisnis
open IDEA_Development_Roadmap.md        # Timeline & milestone
open IDEA_Task_Management.xlsx          # Backlog 200 task

# Buka mockup di browser
open "GUI html/IDEA_Login.html"
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
│   ├── IDEA_Dashboard.html
│   └── ... (35 file lain)
├── .gitignore
└── (future: backend/, frontend/, infra/)
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
