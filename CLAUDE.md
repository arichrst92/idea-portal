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
2. Cek `git status` & `git log -5` — lihat state terakhir
3. Buka `IDEA_Task_Management.xlsx` — cek TSK yang in-progress atau next priority
4. Diskusi sama Ari: lanjut TSK mana?
5. Mulai kerja → push frequently

## Saat Stuck

- Cek `knowledge.md` dulu — kemungkinan ada di spec
- Cek `IDEA_User_Stories.docx` untuk AC
- Cek `IDEA_Negative_Cases.docx` untuk edge case yang harus di-handle
- Cek mockup di `GUI html/` untuk visual reference
- Tanya Ari jika spec ambiguous — jangan asumsi

---

**Last updated:** 2026-05-26 (saat repo setup dari OneDrive → ~/Projects/idea-portal)
