# Smoke Test Guide — M1.1 Auth & RBAC

Checklist verifikasi semua fitur M1.1 yang sudah live di localhost.

## Quick Start

```bash
cd ~/Projects/idea-portal

# Boot semua services (postgres + redis + minio + backend + frontend)
./boot_local.sh

# Buka browser
open http://localhost:5173
```

Login credentials:
- **NIK:** `ADMIN-001`
- **Password:** `admin123`

## Test Checklist

### 1. Backend Health & API Docs

- [ ] `curl http://localhost:8000/health` → `{"status":"ok"}`
- [ ] Buka `http://localhost:8000/docs` → Swagger UI dengan semua auth endpoints
- [ ] Endpoint list: `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me`,
      `/auth/me/permissions`, `/auth/forgot-password`, `/auth/reset-password`,
      `/auth/change-password`, `/auth/audit-logs`, `/auth/executive-ping`,
      `/auth/search`, `/admin/permissions/matrix`, `/admin/users/{nik}/unlock`

### 2. Login Flow (TSK-001 + TSK-002)

- [ ] Buka `http://localhost:5173` → auto-redirect ke `/login`
- [ ] Form validation: submit kosong → error "NIK tidak boleh kosong"
- [ ] Login wrong password → Alert error muncul (NIK atau password tidak valid)
- [ ] Login `ADMIN-001` / `admin123` → redirect ke dashboard
- [ ] DevTools → Application → localStorage → key `idea-auth-storage` berisi access_token + refresh_token
- [ ] Reload page → tetap authenticated (persist)

### 3. AppShell Layout (TSK-009)

- [ ] Sidebar kiri muncul dengan logo "ID" + "IDEA Portal"
- [ ] Menu items: Dashboard, Pengaturan, Permission Matrix (Direktur Utama)
- [ ] Click hamburger icon → sidebar collapse ke 64px
- [ ] Resize window ke < 768px → sidebar hidden, ada menu trigger
- [ ] Click menu trigger di mobile → Drawer slide-in dari kiri
- [ ] User avatar dropdown di kanan atas → menampilkan NIK + role

### 4. RBAC & Executive Endpoints (TSK-003 + TSK-193)

```bash
# Login dulu untuk dapat token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"nik":"ADMIN-001","password":"admin123"}' | jq -r .access_token)

# Test /me
curl http://localhost:8000/api/v1/auth/me -H "Authorization: Bearer $TOKEN"

# Test /me/permissions (harus return ~50+ permissions)
curl http://localhost:8000/api/v1/auth/me/permissions -H "Authorization: Bearer $TOKEN"

# Test /executive-ping (harus respond dengan persona)
curl http://localhost:8000/api/v1/auth/executive-ping -H "Authorization: Bearer $TOKEN"
# Expected: {"message":"Welcome to Executive Portal","persona":"ADMIN-001 (Direktur Utama)","nik":"ADMIN-001"}
```

- [ ] `/me` return user info dengan roles
- [ ] `/me/permissions` return 50+ permissions
- [ ] `/executive-ping` return persona "Direktur Utama" eksplisit

### 5. Permission Matrix (TSK-004)

- [ ] Navigate ke `http://localhost:5173/admin/permissions`
- [ ] Table render dengan rows = permissions, columns = roles
- [ ] Filter by Resource: dropdown muncul, filter bekerja
- [ ] Checkbox di kolom DIREKTUR_UTAMA dan WAKIL_DIREKTUR_UTAMA = **disabled** (lock-out prevention)
- [ ] Checkbox di kolom MANAGER bisa di-toggle → backend update + notification "Permission updated"
- [ ] Cek di `/auth/audit-logs` (lewat /docs) → ada audit log `PERMISSION_GRANTED` / `REVOKED`

### 6. Settings & Theme (TSK-008)

- [ ] Navigate ke `/settings`
- [ ] Section "Tampilan" → ThemeSwitcher (Light / Dark / System)
- [ ] Click "Dark" → seluruh UI berubah dark mode dalam <500ms
- [ ] Click "System" → ikut OS preference
- [ ] Reload page → theme preference persist
- [ ] Font size segment switcher → text size berubah seketika
- [ ] Reduced motion toggle → animasi disabled

### 7. Change Password (TSK-007)

- [ ] Di Settings page, section "Keamanan"
- [ ] Wrong current password → error "Password lama tidak sesuai"
- [ ] Same new = current → error "tidak boleh sama"
- [ ] Confirm tidak match → error "Confirm password tidak sama"
- [ ] Valid input → notification "Password diubah"
- [ ] Logout + login dengan password baru → sukses

### 8. Forgot Password Flow (TSK-007)

- [ ] Logout, di Login page click "Lupa password?"
- [ ] Navigate ke `/forgot-password`
- [ ] Input NIK `NONEXISTENT` → generic message (anti-enumeration), tidak ada token
- [ ] Input NIK `ADMIN-001` → message + reset_token displayed (DEV mode)
- [ ] Click link "Klik di sini untuk reset password" → navigate ke `/reset-password?token=...`
- [ ] Input new password 2x → submit → Result success → auto-redirect /login
- [ ] Login dengan password baru → sukses
- [ ] Kembalikan password ke `admin123` via Settings

### 9. Account Lock (TSK-006)

- [ ] Logout
- [ ] Login dengan wrong password 5x berturut-turut
- [ ] Pada attempt ke-5: Alert berubah dengan **countdown MM:SS** (30:00)
- [ ] Tunggu beberapa detik → countdown decrement
- [ ] Login dengan correct password → tetap ACCOUNT_LOCKED
- [ ] Cek `/auth/audit-logs` → ada `LOGIN_FAILED_INVALID_CREDENTIALS` 5x + `LOGIN_FAILED_ACCOUNT_LOCKED`
- [ ] Untuk unlock: pakai admin endpoint (kalau ada user lain login sbg Direktur):
  ```bash
  curl -X POST http://localhost:8000/api/v1/admin/users/ADMIN-001/unlock \
    -H "Authorization: Bearer $TOKEN"
  ```
- [ ] Atau tunggu 30 min auto-unlock
- [ ] Atau reset via DB: `docker compose exec postgres psql -U idea -d idea_portal -c "UPDATE users SET is_locked=false, failed_login_attempts=0 WHERE nik='ADMIN-001';"`

### 10. Session Management (TSK-005)

- [ ] Login → dashboard
- [ ] DevTools → Network tab
- [ ] Wait 60+ menit (atau ubah `access_token_expire_minutes=1` di .env untuk test cepat)
- [ ] Click apa saja yang trigger API call → otomatis refresh token + retry, no logout
- [ ] DevTools → Application → check refresh_token sudah update di localStorage
- [ ] **Multi-tab test:** buka 2 tab dashboard, logout di tab 1 → tab 2 juga otomatis redirect ke /login + notification "Anda logout dari tab lain"
- [ ] **Idle test:** ubah `IDLE_MINUTES=1` di `frontend/src/lib/sessionManager.tsx` untuk testing, restart Vite, biarkan idle 1 menit → auto-logout + notification

### 11. Global Search (TSK-012)

- [ ] Press **⌘K** (Mac) → modal Global Search muncul, input auto-focused
- [ ] Type "AD" → loading muncul setelah 250ms
- [ ] Results muncul: "ADMIN-001" di group "User"
- [ ] Press ↓ arrow → row highlighted
- [ ] Press Enter → navigate ke `/admin/users/ADMIN-001` (akan 404 karena halaman belum dibuat — itu OK untuk M1.1)
- [ ] Press Esc → modal close
- [ ] Click 🔍 icon di topbar → modal open via custom event
- [ ] Type query < 2 chars → hint message muncul

### 12. Logout Flow (TSK-005)

- [ ] Click user avatar di kanan atas → dropdown menu
- [ ] Click "Logout" → redirect ke `/login`
- [ ] DevTools localStorage → `idea-auth-storage` cleared (atau `isAuthenticated: false`)
- [ ] Cek `/auth/audit-logs` → ada `LOGOUT_SUCCESS` audit log

### 13. Audit Log (TSK-011)

```bash
# Login dulu
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"nik":"ADMIN-001","password":"admin123"}' | jq -r .access_token)

# Get audit logs (latest 10)
curl "http://localhost:8000/api/v1/auth/audit-logs?limit=10" \
  -H "Authorization: Bearer $TOKEN" | jq

# Filter by action
curl "http://localhost:8000/api/v1/auth/audit-logs?action=LOGIN_SUCCESS&limit=5" \
  -H "Authorization: Bearer $TOKEN" | jq
```

- [ ] Endpoint return list dengan `actor_persona` field
- [ ] `actor_persona` untuk ADMIN-001 = `"ADMIN-001 (Direktur Utama)"` ← **EKSPLISIT** (NC-EX-005)
- [ ] Total count > 0 (sudah ada login attempts)

### 14. Permission Denied (RBAC enforcement)

```bash
# Buat user staff manual via DB
docker compose exec postgres psql -U idea -d idea_portal <<SQL
INSERT INTO users (id, nik, password_hash, email, is_active, created_at, updated_at)
VALUES (gen_random_uuid(), 'STAFF-001', '\$2b\$12\$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewfNDjlEkSyDF.IS', 'staff@ide.asia', true, NOW(), NOW())
ON CONFLICT (nik) DO NOTHING;

INSERT INTO user_roles (user_id, role_id, created_at, updated_at)
SELECT u.id, r.id, NOW(), NOW()
FROM users u, roles r
WHERE u.nik = 'STAFF-001' AND r.code = 'STAFF'
ON CONFLICT DO NOTHING;
SQL

# Bcrypt hash di atas adalah hash dari "staff123" (verify via service.verify_password)
```

- [ ] Login sebagai `STAFF-001` / `staff123` → sukses
- [ ] Navigate ke `/admin/permissions` → Result "403 — Executive only"
- [ ] API call `/auth/audit-logs` → 403 PERMISSION_DENIED
- [ ] API call `/auth/executive-ping` → 403 EXECUTIVE_ONLY

### 15. Backend Tests

```bash
cd ~/Projects/idea-portal/backend
source .venv/bin/activate
pytest -v --tb=short
```

- [ ] Expected: **50+ tests passed** (test_auth, test_jwt, test_rbac, test_session, test_password_reset, test_permission_matrix, test_account_lock, test_search)
- [ ] Coverage report di terminal output

## Common Issues

### "Connection refused" saat curl localhost:8000

Cek backend log:
```bash
tail -50 /tmp/idea_portal/backend.log
```

Common: postgres belum healthy, migration error, missing env var.

### Migration error "table already exists"

Reset DB:
```bash
docker compose down -v
./boot_local.sh
```

### Frontend white screen

Cek Vite log:
```bash
tail -50 /tmp/idea_portal/frontend.log
```

Common: TypeScript error, missing import. Fix lalu Vite auto-reload.

### CORS error di browser console

`backend/.env` cek `CORS_ORIGINS=http://localhost:5173,http://localhost:3000`. Restart backend.

## Stop Stack

```bash
./stop_local.sh
```

Data tetap preserved di Docker volumes. Untuk reset penuh:
```bash
docker compose down -v
```

---

**M1.1 capabilities yang sudah live:** 13 TSK, 76 pts, ~50+ tests. Setelah smoke test pass semua, siap lanjut ke M1.2 (Employee & Org Master Data).
