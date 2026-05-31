# CLAUDE.md — Project Context for Claude Sessions

Dokumen ini adalah single source of truth untuk Claude saat bekerja di repo ini. Baca sebelum mulai task.

---

## Identitas Proyek

- **Nama:** IDEA Internal Portal
- **Perusahaan:** PT. Solusi Inovasi Bangsa (IDE Asia)
- **URL:** portal.ide.asia
- **Tipe:** Greenfield ERP + HRIS, web-based, desktop-first
- **Skala:** 50–200 karyawan internal
- **Bahasa:** Indonesia (UI + dokumentasi)

## Tim & Workflow

**Solo dev setup:** Ari Christian (arichrst@ide.asia) + Claude sebagai AI pair programmer.

- Ari = product owner + tech lead + sole developer
- Claude = pair programmer, code generator, reviewer, documentor

## Git Workflow — WAJIB

**Repo:** `git@github.com:arichrst92/idea-portal.git`

### Aturan Push

🔴 **WAJIB push ke remote setiap kali ada perubahan code yang completed.**

Definisi "completed":
- Selesai 1 task (TSK-XXX) → push
- Selesai 1 fitur kecil yang working → push
- Selesai refactor yang tested → push
- Selesai update dokumentasi yang substansial → push

Jangan tunggu sampai banyak commit baru push. Push frequently.

### Commit Message Convention (Conventional Commits)

```
<type>(<scope>): <subject>  [TSK-XXX]

[optional body]
[optional footer]
```

**Type:**
- `feat` — fitur baru
- `fix` — bug fix
- `docs` — dokumentasi
- `style` — formatting, no logic change
- `refactor` — restructure, no behavior change
- `test` — add/update tests
- `chore` — maintenance, deps update
- `perf` — performance improvement

**Scope:** Epic ID (`EP-01`, `EP-02`, dst) atau domain area

**Subject:** Bahasa Indonesia atau English, present tense, lowercase, no period

**Examples:**
```
feat(EP-01): implement JWT auth with refresh token  [TSK-002]
fix(EP-05): correct PPh21 calc for variable income  [TSK-048]
docs: update knowledge.md sec 7 commission rule
feat(EP-07): add Gantt chart view to project page   [TSK-065]
chore: bump fastapi to 0.110, sqlalchemy to 2.0.30
```

### Branch Convention

- `main` — selalu production-ready, di-push langsung untuk solo dev (no PR review needed, tapi bisa pakai PR jika mau)
- `feature/EP-XX-description` — opsional, untuk fitur besar yang multi-commit
- `fix/TSK-XXX-description` — opsional untuk bug fix yang non-trivial

Solo dev = OK push langsung ke main untuk speed, tapi pertimbangkan branch untuk:
- Eksperimen yang mungkin di-revert
- Refactor besar yang multi-day

### Sebelum Push, Selalu

1. `git status` — pastikan tahu apa yang berubah
2. `git diff` — review changes
3. Run tests (jika ada): `pytest` (backend) atau `npm test` (frontend)
4. Run linter: `ruff check` atau `eslint`
5. `git add` selektif (jangan `git add .` membabi buta — cek dulu yang masuk)
6. Commit dengan message proper
7. `git push origin main`

---

## File Structure

```
idea-portal/
├── README.md                        # Project overview untuk publik
├── CLAUDE.md                        # ← Anda baca ini
├── knowledge.md                     # MASTER SPEC (21 section) — source of truth #1
├── IDEA_Development_Roadmap.md      # Timeline & milestone — source of truth #2
├── IDEA_Task_Management.xlsx        # Backlog 200 task — source of truth #3
├── IDEA_User_Stories.docx           # Acceptance criteria 46 stories
├── IDEA_Negative_Cases.docx         # Edge case 45 grup / ~216 cases
├── GUI html/                        # 37 UI mockup HTML (visual reference)
├── backend/                         # FastAPI app (TBD, start di PH1 M1.1)
├── frontend/                        # React app (TBD, start di PH1 M1.1)
├── infra/                           # Docker, deployment configs (TBD)
└── .gitignore
```

## Source of Truth Priority

Saat ada konflik antara dokumen:
1. **`knowledge.md`** menang untuk spec & aturan bisnis
2. **`IDEA_Development_Roadmap.md`** menang untuk timeline & milestone
3. **`IDEA_Task_Management.xlsx`** menang untuk task tracking & status
4. **`IDEA_User_Stories.docx`** untuk detailed AC per fitur
5. **`IDEA_Negative_Cases.docx`** untuk validation & edge case
6. **`GUI html/*.html`** untuk visual reference (sudah konsisten dengan spec post v2 review)

Jika ada perbedaan, **update dokumen yang lebih rendah** ke spec yang lebih tinggi, atau diskusikan dengan Ari dulu.

## Aturan Kunci yang Sering Lupa

Ini aturan critical dari `knowledge.md` yang sering kelupaan saat coding:

### Identity & Auth
- **Login pakai NIK**, bukan email. Email ada di profil tapi tidak untuk login (`knowledge.md` sec.1)
- **Wakil Direktur Utama = role terpisah** dengan permission identik Direktur Utama. Audit log WAJIB record persona name eksplisit, bukan generic "Direktur" (NC-EX-005 critical)
- RBAC enforce di **API level**, bukan hanya UI hide

### Approval
- **Semua request = 2 lapis approval** (atasan langsung → GM/C-Level)
- Self-approval = blocked
- Sequential: Layer 2 tidak boleh approve sebelum Layer 1

### Assessment & SP
- Score = `(OKR × bobot%) + (Weighted × bobot%)` dengan bobot per dept by GM/C-Level
- Threshold flag: bln-1 kuning, bln-2 oranye, bln-3 → **SP otomatis trigger**
- **SP-O (Outsource SP) ≠ SP internal**. SP-O dipicu client complaint, sequence SP-O1/O2/O3, SP-O3 = replacement
- SP3 internal = trigger layoff (perlu approval)

### Payroll
- Reimbursement = **transfer terpisah**, bukan via payroll
- Multi-currency: setiap transaksi simpan nominal asli + kurs + IDR equiv
- THR = configurable, transfer terpisah
- Komisi Sales dari Closed Won (sales PIC) → **auto-create variable line di payroll**. Direktur-driven deal = no commission

### Project
- 3 tipe: Client (revenue), Internal (OPEX/CAPEX cost), R&D (sub-internal)
- Invoice termin: setup saat kick-off, **notif Finance otomatis** saat milestone tercapai
- Direktur Utama bisa override close project kapan saja (wajib input alasan)

### Outsource
- BA = digital signature via token unik, client buka tanpa login
- Billing 2 tipe: flat/bulan ATAU per hari kerja (timesheet × rate)

---

## Konvensi Coding

### Python (Backend)
- Style: PEP 8, formatter **ruff** (config di `pyproject.toml`)
- Type hints **wajib** untuk function signatures
- Async/await untuk I/O-bound code (FastAPI)
- SQLAlchemy 2.0 syntax (no legacy 1.x style)
- Test framework: pytest
- File organization: domain-driven (per dept domain: `app/identity/`, `app/payroll/`, dst)

### TypeScript (Frontend)
- Strict mode ON di tsconfig
- Functional components + hooks (no class components)
- State: Zustand untuk global, React Query untuk server state
- Form: React Hook Form + Zod validation
- Style: Tailwind via Ant Design built-in, no inline style except di mockup
- File organization: feature-based (`features/payroll/`, `features/assessment/`)

### Naming
- Snake_case untuk Python (variable, function), PascalCase untuk class
- camelCase untuk TS (variable, function), PascalCase untuk component/type
- Database: snake_case, plural untuk tabel (`employees`, `payroll_slips`)
- API endpoints: kebab-case path, plural noun (`/api/v1/employees`)

### Commit-able Output

Saat Claude code:
- Selalu sertakan tests untuk logic baru
- Update relevant docs (knowledge.md jika spec berubah, README jika setup berubah)
- Run linter sebelum commit
- Cantumkan TSK ID di commit message
- Push ke remote setelah commit

---

## Decision Log

Catat decision penting yang ditemukan saat development di sini:

| Date | Decision | Reason |
|---|---|---|
| 2026-05-26 | NIK sebagai login identifier (bukan email) | UI mockup sudah pakai NIK, lebih natural untuk karyawan internal |
| 2026-05-26 | Wakil Direktur Utama = role terpisah di RBAC (bukan inherit dari Direktur) | Audit clarity — persona name harus eksplisit |
| 2026-05-26 | SP-O (Outsource SP) flow terpisah dari SP internal | Trigger berbeda: client complaint vs score penilaian |
| 2026-05-26 | TSK-110 dihapus (duplikat TSK-148 untuk SP-O) | Cleanup task backlog |
| 2026-05-27 | UUID v4 primary key untuk semua tabel | Distributed-system safe, no leaking sequential info, FK cleaner |
| 2026-05-27 | Soft delete via `deleted_at` (TimestampMixin + SoftDeleteMixin) | Per NC-SYS-001-06: financial-linked records harus archive, bukan hard delete |
| 2026-05-27 | JWT HS256 dengan token type claim (`access` vs `refresh`) | Cegah refresh token dipakai sebagai access (security hardening) |
| 2026-05-27 | Refresh token rotation di TSK-002 tanpa blacklist | Simple — blacklist akan ditambah di TSK-005 dengan Redis store |
| 2026-05-27 | Frontend axios interceptor: queue concurrent 401 saat refresh in-flight | Cegah refresh storm; semua pending requests retry sekaligus setelah refresh sukses |
| 2026-05-27 | Theme tokens via CSS variables di document.documentElement | Non-AntD components bisa reference --blue/--bg langsung; sync dengan AntD ConfigProvider |
| 2026-05-27 | Breakpoint: mobile <768px, tablet 768-1024px, desktop >1024px | Sesuai AntD default; useResponsive hook untuk component-level branch |
| 2026-05-27 | Global search permission-aware di backend (Staff hanya self) | Cegah unauthorized user enumeration; lihat search.py |
| 2026-05-27 | M1.1 Auth & RBAC: 76 pts complete dalam 7 sesi (avg 10-13 pts/sesi) | Velocity solo+AI lebih tinggi dari estimasi 12-18 pts/sprint; bisa accelerate ke Skenario A roadmap |
| 2026-05-28 | Register semua domain models di `app/main.py` (identity, organization, assessment, project, outsource, payroll, sales) | SQLAlchemy mapper config butuh resolve cross-domain relationship saat first query (User.employee → Employee). Tanpa eager import muncul `InvalidRequestError: 'Employee' failed to locate a name`. Pattern: import semua di app entry point. |
| 2026-05-28 | `User.roles` relationship butuh `foreign_keys="UserRole.user_id"` eksplisit | `user_roles` table punya 2 FK ke `users.id` (user_id PK + assigned_by_user_id audit). SQLAlchemy ambiguous tanpa hint. |
| 2026-05-28 | Pin `bcrypt>=4.0.0,<4.1.0` di pyproject | bcrypt 5.x hapus `__about__` attribute yang dipakai passlib untuk version detection. passlib gagal init dan crash semua password hashing. Pin sampai passlib release fix atau migrate ke bcrypt direct. |
| 2026-05-28 | Docker postgres → port 5433 (bukan 5432) | Mac mini punya postgres native di 5432 yang shadow Docker. Untuk hindari kill postgres user (mungkin dipakai project lain), Docker IDEA Portal pakai 5433. Update di docker-compose.yml + backend/.env. |
| 2026-05-28 | UI polish per epic, BUKAN dedicated sprint UI | M1.1 frontend dibangun pakai AntD bare-bones tanpa visual port dari `GUI html/*.html`. Setiap port halaman baru di milestone berikutnya WAJIB ambil styling (colors, typography, layout, shadows, gradient mesh) langsung dari mockup HTML. Halaman M1.1 yang sudah ada (Login, AppShell, Settings, PermissionMatrix, GlobalSearch) di-polish belakangan saat ada kapasitas. Mockup HTML = source of truth visual. |
| 2026-05-28 | VPS production stack pakai Docker Compose, dibangun setelah M1.2 selesai | `start.sh` cuma dev tool (uvicorn --reload + vite dev). Production stack akan: backend Dockerfile (gunicorn + uvicorn workers), frontend Dockerfile (npm build → nginx), docker-compose.prod.yml, Caddy reverse proxy + auto HTTPS, .env.prod, deploy.sh. Defer ke setelah M1.2 (101 pts) supaya ada cukup fitur demo-able sebelum invest deployment effort. |
| 2026-05-29 | Project Management hierarchy: `Phase > Epic > Task > Sub Task` (4 level, ganti Milestone → Phase) | Spec sebelumnya cuma Project + Milestone + Task — kurang granular untuk delivery besar. Phase = release/wave, Epic = group of related tasks, Task = unit kerja, Sub Task = breakdown. Milestone hilang (digabung ke Phase yg juga punya target_date). |
| 2026-05-29 | Slug Jira-style (`{PROJECT_CODE}-{counter}`) auto-generate per project | Slug human-readable untuk reference cepat ("WEB-123"). Counter atomic per project via `select max + 1 with row lock`. Applies to Task & Subtask. |
| 2026-05-29 | Story point free integer (no Fibonacci/t-shirt) | User pilih bebas — flexibility lebih penting drpd standardisasi di tahap awal. Bisa diketatkan ke Fibonacci nanti kalau perlu. |
| 2026-05-29 | Comment markdown via `react-markdown` di frontend, plain text storage di DB | Format ringan tanpa overengineering rich editor. Storage = text mentah, render = markdown di UI. Comment accessible langsung dari kanban card (icon + count badge → drawer/modal). |
| 2026-05-29 | Invoice dipindah dari `app/project/` ke `app/finance/` (new domain) | Conceptually invoice belongs to Finance (lihat mockup `IDEA_InvoiceAR.html`). Project hanya trigger lewat Phase completion. Tabel baru `invoices` di Finance dengan FK `project_id` & `trigger_phase_id` nullable. Endpoint pindah `/api/v1/finance/invoices/*`. |
| 2026-05-29 | TSK numbering untuk re-work modul: append alphabet (TSK-022B, TSK-022C, …) | TSK-022 sudah COMPLETED — refactor besar di-track sebagai sub-task baru. Lebih clean drpd reopen TSK existing. |
| 2026-05-31 | Imperative AntD API (`message`, `Modal.confirm`, `notification`) WAJIB lewat `@/lib/notify` proxy, BUKAN import langsung dari `antd` | AntD v5 deprecate static call — tidak pickup dynamic theme/locale/prefixCls dari `ConfigProvider`. Pola: `lib/notify.ts` proxy + `NotifyBinder` (mount di `AppRoutes`) yang call `bindNotifyApi(App.useApp())`. JSX `<Modal>` component tetap dari `antd`; hanya imperative call yang migrate. Audit via `outputs/audit_frontend.py` (kategori A3). |
| 2026-05-31 | AntD v5 deprecated props sweep: `destroyOnClose` → `destroyOnHidden`, `Dropdown overlay=` → `Dropdown menu={{ items: [...] }}` | Bulk sed safe untuk destroyOnClose (43 occurrences fixed). Dropdown overlay perlu refactor manual karena ganti dari JSX `<Menu>` ke items array. |
| 2026-05-31 | Frontend audit script `outputs/audit_frontend.py` re-runnable, 4 kategori (A1 hooks-after-return, A2 deprecated AntD, A3 static notify, A4 InputNumber parser) | Jalankan sebelum push setelah refactor besar untuk catch regression. A3 detector skip kalau import sudah dari `@/lib/notify` (proxy aman). |
| 2026-05-31 | WeasyPrint import WAJIB lazy (di dalam function body), bukan top-level | Native libs (pango, glib) tidak selalu ada di host (mis. macOS dev box tanpa Homebrew install). Top-level import crash backend startup. Pattern: `def generate_pdf(): from weasyprint import HTML; ...` plus actionable error message kalau import fail. |
| 2026-05-31 | Kembali ke sprint discipline — kerja per Sprint goal, bukan TSK-pick-and-choose | Marathon mode 28-31 May bypass roadmap (jump ke PH2 modul sambil M1.4 baru 37%). Formalkan Sprint Planning di xlsx: S1 (1-14 Jun) close M1.4 core, S2 (15-28 Jun) M1.4 variants + M1.2 UI, S3 (29 Jun-12 Jul) M1.3 closure, S4 (13-26 Jul) PH1 GATE demo. Setiap sprint = goal terikat milestone, end-of-sprint demo. Tidak skip milestone berikutnya sebelum current closure. |

Tambah row baru saat ada keputusan signifikan.

---

## Quick Reference — Endpoint Mapping (Future)

Saat coding, gunakan pattern ini untuk endpoint:

```
POST   /api/v1/auth/login                    # NIK + password → JWT
POST   /api/v1/auth/refresh                  # refresh token

GET    /api/v1/employees                     # list with filters
POST   /api/v1/employees                     # create (with bulk option)
GET    /api/v1/employees/{nik}               # detail
PATCH  /api/v1/employees/{nik}               # update
POST   /api/v1/employees/{nik}/promote       # promotion flow
POST   /api/v1/employees/{nik}/mutate        # mutation flow

POST   /api/v1/payroll/run                   # trigger payroll run
GET    /api/v1/payroll/slips/{nik}/{period}  # slip detail

... (akan diperluas saat development)
```

---

## Saat Memulai Sesi Baru

1. Baca file ini (`CLAUDE.md`)
2. **🚨 BACA `ERD_REFERENCE.md`** — canonical model field map. WAJIB sebelum menulis query atau mengakses model attribute. Banyak FK direction counter-intuitive (Employee.nik tidak ada, User.employee_id tidak ada — lihat reference).
3. Cek `git status` & `git log -5` — lihat state terakhir
4. Buka `IDEA_Task_Management.xlsx` — cek TSK yang in-progress atau next priority
5. Diskusi sama Ari: lanjut TSK mana?
6. Mulai kerja → push frequently

## Aturan Coding Wajib (Prevent Past Bugs)

🔴 **ERD Compliance (NC-DEV-001):** Sebelum write SQLAlchemy query atau access `.attr` pada model instance, WAJIB verify field exists di `ERD_REFERENCE.md`. Pattern yang sering salah:
- ❌ `Employee.nik` (Employee tidak punya kolom nik — NIK ada di User table)
- ❌ `User.employee_id` (User tidak punya employee_id — Employee.user_id is the FK)
- ❌ `User.full_name`, `User.department_id` (semua di Employee, bukan User)

Workflow: Saat butuh data dari Employee + User → JOIN `Employee.user_id == User.id`.

🔴 **Route Order (NC-DEV-002):** FastAPI matches routes in declaration order. Static routes (`/projects/my-tasks-due`) yang muncul SETELAH dynamic routes (`/projects/{id}`) akan ke-shadow → 422 validation error. Solusi: declare static route di atas, atau pakai namespace berbeda (`/me/project-tasks-due`).

🔴 **Migration Discipline:** Setiap model baru WAJIB ada migration alembic. Tambah model import di `alembic/env.py`. Run `./tsk022b_apply.sh` (idempotent) untuk apply.

🔴 **Audit Script:** Saat curiga ada attribute error, jalankan `outputs/audit_models.py` dan `outputs/audit_usage.py`. Lihat `ERD_REFERENCE.md` section "Audit Workflow".

🔴 **Permission Codes (NC-DEV-003):** Setiap `require_permission("x.y")` WAJIB match dengan code yang terdaftar di `app/identity/permissions.py` PERMISSIONS list. Code yang tidak terdaftar = 403 untuk SEMUA user. Jalankan `outputs/audit_permissions.py` untuk verify. Past examples: `project.close` (tidak ada — pakai `project.override`), `employee.delete` (tidak ada — pakai `employee.edit`).

🔴 **Frontend Hooks Order (NC-DEV-004):** Hook calls (`useState`, `useWatch`, `useMemo`, `useQuery`) HARUS dipanggil sebelum conditional early return. React error "Rendered more hooks than during the previous render" terjadi kalau hook setelah `if (!x) return null`. Solusi: pindah semua hook ke atas, conditional return paling akhir sebelum JSX.

🔴 **AntD Imperative API (NC-DEV-005):** JANGAN import `message`, `notification`, atau pakai `Modal.confirm/.warning/.info/.success/.error` langsung dari `antd`. Browser console akan warn "Static function can not consume context like dynamic theme" dan toast tidak ke-pickup theme/locale dari `ConfigProvider`. Pola yang benar:
```tsx
import { message, modal, notification } from '@/lib/notify';
message.success('OK');
modal.confirm({ title: 'Hapus?', onOk: () => {} });
```
JSX component `<Modal>` TETAP dari `antd` — hanya imperative call yang migrate. Proxy di-bind via `NotifyBinder` (sudah mount di `AppRoutes`). Audit: `python3 outputs/audit_frontend.py` → kategori A3 harus 0.

🔴 **AntD Deprecated Props (NC-DEV-006):** Saat copy code dari mockup lama atau snippet AI lain, cek deprecation:
- `destroyOnClose` (Modal/Drawer) → **`destroyOnHidden`**
- `Dropdown overlay={<Menu items=[…] />}` → **`Dropdown menu={{ items: […] }}`**
- `Dropdown dropdownRender={...}` → **`Dropdown popupRender={...}`**
- `<Spin tip="..." />` self-closing → wrap children `<Spin tip="..."><div style={{minHeight:24}}/></Spin>` atau pakai `fullscreen`
Audit kategori A2 di `outputs/audit_frontend.py` harus 0 sebelum push.

🔴 **WeasyPrint Lazy Import (NC-DEV-007):** Top-level `from weasyprint import HTML` crash backend startup di host tanpa native libs (pango, glib). Pattern wajib:
```python
def generate_slip_pdf(...):
    try:
        from weasyprint import HTML
    except ImportError as e:
        raise RuntimeError("PDF generator butuh `brew install pango glib cairo`...") from e
    HTML(string=html).write_pdf(...)
```

## Saat Stuck

- Cek `ERD_REFERENCE.md` untuk model field map
- Cek `knowledge.md` untuk spec bisnis
- Cek `IDEA_User_Stories.docx` untuk AC
- Cek `IDEA_Negative_Cases.docx` untuk edge case yang harus di-handle
- Cek mockup di `GUI html/` untuk visual reference
- Tanya Ari jika spec ambiguous — jangan asumsi

---

**Last updated:** 2026-05-31 (NC-DEV-005/006/007 added + frontend audit script + AntD notify proxy)
