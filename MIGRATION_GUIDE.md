# Migration Guide — OneDrive → Local Mac

**Pindahkan project IDEA Portal dari OneDrive ke `~/Projects/idea-portal/` + push ke GitHub.**

---

## TL;DR

```bash
# Buka Terminal, jalankan:
cd "/Users/idea/Library/CloudStorage/OneDrive-IDEAsia/IDEA Portal (1)"
./migrate_to_local.sh

# Setelah selesai:
cd ~/Projects/idea-portal
open .
```

Selesai. Script handle semua: copy + git init + remote + commit + push.

Kalau ada error, baca section yang relevan di bawah.

---

## Pre-flight Check (5 menit)

Sebelum jalankan script, pastikan **3 hal**:

### 1. GitHub Repo Sudah Dibuat

Buka https://github.com/new dan buat repo:

| Field | Value |
|---|---|
| Owner | `arichrst92` |
| Repository name | `idea-portal` |
| Visibility | **Private** (recommended untuk internal company project) |
| Initialize | **KOSONGKAN semua** — jangan add README/license/.gitignore (kita push dari local) |

Setelah create, **jangan klik apa-apa** di GitHub. Pulang ke Terminal.

### 2. SSH Key Sudah Ter-Add ke GitHub

Test SSH connection:

```bash
ssh -T git@github.com
```

Expected output:
```
Hi arichrst92! You've successfully authenticated, but GitHub does not provide shell access.
```

Kalau dapat "Permission denied":

```bash
# Cek SSH key yang ada
ls -la ~/.ssh/

# Kalau belum ada id_ed25519.pub atau id_rsa.pub:
ssh-keygen -t ed25519 -C "arichrst@ide.asia"
# (tekan Enter untuk semua default)

# Copy public key ke clipboard
pbcopy < ~/.ssh/id_ed25519.pub

# Buka GitHub → Settings → SSH and GPG keys → New SSH key
# Title: "Mac mini IDEA dev"
# Paste key, save.
```

Test lagi `ssh -T git@github.com` — sampai dapat "successfully authenticated".

### 3. Git Sudah Terinstall

```bash
git --version
# Expected: git version 2.39+ (atau lebih baru)
```

Kalau belum install:

```bash
# Install Xcode Command Line Tools (akan auto-install git)
xcode-select --install

# Atau via Homebrew (lebih up-to-date)
brew install git
```

---

## Jalankan Migration

Setelah 3 pre-flight check di atas hijau semua:

```bash
# 1. Buka Terminal, ke folder OneDrive
cd "/Users/idea/Library/CloudStorage/OneDrive-IDEAsia/IDEA Portal (1)"

# 2. Pastikan script executable
chmod +x migrate_to_local.sh

# 3. Jalankan
./migrate_to_local.sh
```

Script akan:

1. **Preflight check** — verify source, git, rsync, ssh
2. **Create folder** `~/Projects/idea-portal/`
3. **Copy files** dari OneDrive (exclude .DS_Store, backup, lock files, script itu sendiri)
4. **Init git** + set user.name + user.email
5. **Add remote** `git@github.com:arichrst92/idea-portal.git`
6. **Initial commit** dengan summary lengkap (37 mockup, 200 task, dst)
7. **Push ke GitHub** branch `main`

Durasi total: **~2-5 menit** tergantung kecepatan disk.

---

## Verify Setelah Migration

```bash
# Cek folder lokal
cd ~/Projects/idea-portal
ls -la

# Expected: 37 file HTML di GUI html/, 5 docs root, dst.

# Cek git status
git status
# Expected: "On branch main, nothing to commit, working tree clean"

git log --oneline
# Expected: 1 commit "Initial: design phase complete..."

git remote -v
# Expected:
# origin  git@github.com:arichrst92/idea-portal.git (fetch)
# origin  git@github.com:arichrst92/idea-portal.git (push)

# Buka GitHub di browser
open https://github.com/arichrst92/idea-portal
# Expected: semua file sudah keliahatan di repo
```

---

## Setelah Migration — Switch Cowork ke Folder Baru

Saat ini Cowork (Claude) sedang mount folder OneDrive. Setelah migrasi:

1. **Di Cowork app** — un-mount folder OneDrive lama
2. **Mount folder baru** → pilih `~/Projects/idea-portal/`
3. Cowork akan re-index file di lokasi baru

Setelah ini, semua sesi Claude akan langsung kerja di repo lokal yang sudah terhubung ke GitHub.

---

## OneDrive Cleanup (Pilihan)

Saya sarankan **rename, jangan hapus**, untuk archive 30 hari:

```bash
SOURCE="/Users/idea/Library/CloudStorage/OneDrive-IDEAsia/IDEA Portal (1)"
mv "$SOURCE" "${SOURCE}.archived-$(date +%Y%m%d)"
```

Hasilnya: `IDEA Portal (1).archived-20260526/` — terlihat jelas ini archive, tidak akan ke-edit accidentally.

Setelah 30 hari (sekitar 25 Jun 2026), jika semua sudah aman di GitHub + local, baru hapus archived folder. OneDrive akan auto-sync penghapusan ke cloud.

**JANGAN hapus folder OneDrive segera** — tunggu minimal 1 minggu untuk pastikan migrasi sukses penuh.

---

## Troubleshooting

### Error: "Permission denied (publickey)"
SSH key belum di-setup. Lihat **Pre-flight Check #2** di atas.

### Error: "repository not found"
GitHub repo belum dibuat. Lihat **Pre-flight Check #1** di atas.

### Error: "rsync command not found"
Aneh — rsync ada di macOS default. Coba:
```bash
which rsync
# Kalau kosong, install via brew:
brew install rsync
```

### Error: "git push rejected"
Mungkin repo di GitHub bukan empty (sudah ada commit). Force push (HATI-HATI):
```bash
cd ~/Projects/idea-portal
git push -u origin main --force
```

### Disk space tidak cukup
Cek free space:
```bash
df -h ~
```
Project sekarang ~1.2 MB, tidak masalah. Tapi setelah ada node_modules+venv, akan jadi 2-5 GB. Pastikan punya min. 20 GB free di disk.

---

## Setelah Migration: Repo Structure

```
~/Projects/idea-portal/
├── .gitignore                          ← Python+Node+macOS ignore rules
├── README.md                           ← Project intro (GitHub homepage)
├── CLAUDE.md                           ← Context untuk AI sessions
├── knowledge.md                        ← Master spec (21 section)
├── IDEA_Development_Roadmap.md         ← Timeline 14 bulan
├── IDEA_Task_Management.xlsx           ← 200 task backlog
├── IDEA_User_Stories.docx              ← 46 stories
├── IDEA_Negative_Cases.docx            ← 45 NC grup
├── GUI html/                           ← 37 mockup
│   ├── IDEA_Login.html
│   └── ... (36 file lain)
├── migrate_to_local.sh                 ← (script ini, sudah di-exclude di .gitignore? cek)
└── MIGRATION_GUIDE.md                  ← (file ini)

(future, dibuat saat Sprint 0)
├── backend/                            ← FastAPI app
│   ├── app/
│   ├── tests/
│   ├── pyproject.toml
│   └── ...
├── frontend/                           ← React + Vite + TS
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── ...
├── infra/                              ← Docker, deployment
│   ├── docker-compose.yml
│   ├── nginx/
│   └── ...
└── .env.example                        ← Environment variable template
```

---

## Next Steps (Sprint 0 — 1-7 Jun 2026)

Setelah migration, mulai Sprint 0 sesuai roadmap M1.0:

1. **Day 1 (Senin 1 Jun):** Buka VS Code/Cursor di `~/Projects/idea-portal/`. Buka diskusi dengan Claude untuk break-down TSK-001 (Single Login Portal Setup).
2. **Day 2-3:** Setup `backend/` skeleton — FastAPI + PostgreSQL + Alembic + pytest.
3. **Day 3-4:** Setup `frontend/` skeleton — Vite + React + TS + Ant Design + React Query.
4. **Day 5:** Setup `infra/docker-compose.yml` — services: postgres, redis, minio, backend, frontend.
5. **Day 6:** Smoke test `docker compose up` semua service jalan + hello-world API responsive.
6. **Day 7:** Sprint 0 retro + Sprint 1 planning (M1.1 Auth & RBAC).

Commit + push **setiap hari** sesuai aturan di `CLAUDE.md`.

---

## Help

Stuck? Tanya Claude di Cowork. Buka file `CLAUDE.md` sebagai context, lalu jelaskan masalah. Claude punya semua context project (spec, tasks, mockup, roadmap).

🚀 **Selamat berjuang, semoga 14 bulan ke depan productive!**

---

**Last updated:** 2026-05-26
