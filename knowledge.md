# IDEA Internal Portal — Knowledge Base
**PT. Solusi Inovasi Bangsa (IDE Asia)**
**URL:** portal.ide.asia
**Tipe:** Greenfield ERP + HRIS — Web-based, Desktop-first

---

## 1. Fondasi Sistem

| Aspek | Keputusan |
|---|---|
| Tipe | Greenfield, web-based |
| URL | portal.ide.asia |
| Login | Tunggal, tampilan disesuaikan role |
| Login Identifier | **NIK** (Nomor Induk Karyawan). Email disimpan di profil tapi BUKAN untuk login. |
| Skala | 50–200 karyawan internal |
| Notifikasi | In-app only |
| Bahasa | Indonesia |

---

## 2. Hierarki & Role

```
Level 1 → Direktur Utama + Wakil Direktur Utama (setara, equal authority)
Level 2 → C-Level (CTO, COO, CMO, CFO)
Level 3 → General Manager (GM)
Level 4 → Manager
Level 5 → Lead
Level 6 → Staff
```

**Aturan:**
- Satu karyawan = satu departemen
- Jabatan fungsional = level hierarki (tidak dipisah)
- Approval semua request = 2 lapis (atasan langsung → GM/C-Level)
- Executive Portal = Direktur Utama + Wakil Direktur Utama
- Wakil Direktur = kewenangan identik Direktur, akses penuh Executive Portal

**Role Wakil Direktur Utama — Detail Permission:**
- RBAC engine: Wakil Direktur Utama = ROLE terpisah dengan permission **identik** Direktur Utama (bukan inherit, agar audit trail jelas siapa yang melakukan aksi)
- Kedua role dapat: Close deal langsung, override project status, approve internal project, akses semua dashboard Executive
- Aksi sensitif (close deal, project override, layoff approve) **wajib log nama persona** (Direktur Utama / Wakil Direktur Utama) di audit_logs
- Jika konflik aksi simultan (mis. dua-duanya approve sama bersamaan), **first-write-wins** + notifikasi ke yang kalah
- Saat salah satu cuti panjang, yang lain otomatis menjadi sole authority — tidak ada delegasi ke C-Level

**Approval Flow:**
```
Request dibuat → Lapis 1: Atasan langsung → Lapis 2: GM/C-Level → Approved/Rejected → Notif
```

---

## 3. Departemen

4 departemen utama:
1. **Teknologi** — project management, penilaian, dokumentasi
2. **Operation** — hiring, payroll, outsource, SP, onboarding
3. **Sales & Marketing** — leads, proposal, target, report
4. **Finance & Tax** — transaksi, laporan keuangan, pengadaan

---

## 4. Entitas Data Inti

```
Employee        → Internal (Type A) | Outsource-IDEA placed at client (Type B) | Outsource-kontrak eksternal (Type C)
Organization    → Dept + Level + Hierarki tree
Project         → Multi-member, Kanban + Gantt, 3 tipe: Client / Internal / R&D
Client          → Linked ke Outsource Placement
OutsourcePlacement → Per orang, timesheet per bulan + BA per bulan
```

---

## 5. Modul Dept. Operation

| Modul | Detail Kunci |
|---|---|
| Hiring | Internal job board, tracking end-to-end, offering letter |
| Layoff | Request → approval 2 lapis → offboarding checklist |
| SP (Internal) | AI draft otomatis (score <60 × 3 bln) + manual, SP3 → trigger layoff (perlu approval) |
| SP-O (Outsource) | SP khusus karyawan outsource, dipicu dari complaint client (lihat sub-section di bawah) |
| Outsource Mgmt | Monitor per orang per client, timesheet + BA per bulan (digital signature) |
| Client Complaint | Sales PIC log complaint → notif Operation → coordinate → SP-O issue |
| Payroll | Kompleks: fixed + variable + potongan, output rekap PDF + slip gaji |
| Onboarding | Checklist otomatis post-hired, sambutan perusahaan |
| Assignment Role | Assign dept, level, atasan, audit trail perubahan |
| Promosi | Operation proses atas arahan GM/C-Level, suggest range gaji per level, audit trail |
| Mutasi Antar Dept | Operation initiate atas arahan manajemen, penilaian lama tetap di history |
| Work Calendar | Set working days + national/joint holidays, dept override, affects payroll & leave |
| PKWT/PKWTT Tracking | Alert H-30 & H-7 sebelum kontrak berakhir ke atasan langsung + Operation |

### Sub-section: SP-O (Surat Peringatan Outsource)

Flow SP-O **terpisah** dari SP internal (SP1/SP2/SP3) karena karyawan outsource bekerja di client site dan SP-nya dipicu oleh complaint client, bukan score penilaian internal.

**Trigger:** Client complaint dilaporkan Sales PIC → notif Operation → koordinasi → SP-O issue.

**Tingkatan:**
```
SP-O1 = Warning + coaching (1x kesempatan perbaikan, eval 2 minggu)
SP-O2 = Final warning + 2-week evaluation intensif
SP-O3 = Replacement recommendation → trigger proses cari kandidat pengganti
```

**Aturan:**
- Sequence enforcement: SP-O3 hanya boleh setelah SP-O1 dan SP-O2 di-record
- Approval: Operation issue + GM Operation approve
- SP-O3 = otomatis trigger placement replacement workflow (cari kandidat baru, koordinasi end placement)
- Karyawan outsource dapat melihat SP-O di portal mereka + acknowledge digital

---

## 6. Modul Dept. Teknologi

| Modul | Detail Kunci |
|---|---|
| Project Mgmt | Kanban + Gantt, multi-project per karyawan, allocation %, PM input task |
| Employee Mgmt | Hanya dept Teknologi, workload & availability view |
| Penilaian | Weighted Scoring + OKR, bulanan, threshold <60 × 3 bln |
| Dokumentasi | Per project, versioning, akses member only |
| Report | Per karyawan, export PDF, akses berjenjang |

**Model Penilaian:**
```
Final Score = (OKR × bobot%) + (Weighted × bobot%)
OKR         = pencapaian Key Results (set per kuartal, evaluasi bulanan)
Weighted    = Attitude + Kehadiran + Kolaborasi
Bobot       = dikonfigurasi GM/C-Level per dept
Threshold   = score < 60 × 3 bulan berturut → trigger SP otomatis
Flag kuning = bulan ke-1 (<60)
Flag oranye = bulan ke-2 (<60)
SP trigger  = bulan ke-3 (<60)
```

---

## 7. Modul Dept. Sales & Marketing

| Modul | Detail Kunci |
|---|---|
| Leads Funnel | Per services, 6 stage, assign + reassign ke sales |
| Action Item (AI) | AI-generated per lead per stage, accept/edit/ignore — punya user story sendiri (US-SM-005) |
| Report | Win rate per sales + per services, vs target |
| Target | Individu + tim departemen, alert <50% di tengah bulan |
| Proposal | Template per services, versioning, approval sebelum kirim, export PDF via email |
| Komisi → Payroll | Closed Won otomatis create draft variable line di payroll bulan berjalan (sales PIC saja, bukan Direktur-driven) |

**Funnel Stage:** Prospect → Qualified → Proposal → Negotiation → Closed Won/Lost

**Direktur Closing:**
- Direktur bisa close deal langsung tanpa melalui Sales PIC
- Tidak ada komisi jika Direktur yang close
- Dicatat sebagai "Direktur-driven deal" di laporan
- Leads dari Direktur masuk pipeline Sales seperti biasa

**Lost Deal:** Bisa reopen sebagai lead baru, history interaksi lama tetap tersimpan

**Referral:** Siapa yang refer dicatat, reward masuk komponen variable payroll

---

## 8. Modul Dept. Finance & Tax

| Modul | Detail Kunci |
|---|---|
| Transaksi Harian | Accrual basis, multi-currency, attach bukti, Status: Draft→Verified→Posted |
| Laporan Keuangan | P&L, Neraca, Cash Flow, Pajak — PDF + Excel |
| Reimbursement | Submit → approval 2 lapis → Finance verifikasi → transfer terpisah (bukan via payroll) |
| Payroll | Triggered dari Operation, input ke transaksi, publish slip gaji |
| Pengadaan | Request → approval → Finance verifikasi → asset register jika perlu |

**Multi-currency:** Setiap transaksi: nominal asli + kurs + IDR equivalent

**IDEA adalah PKP:** PPN 11% di invoice ke client, sistem rekap saja, pelaporan manual

**Sub-contractor:** Dicatat di project + Finance sebagai pengeluaran biasa

---

## 9. Executive Portal

Akses: Direktur Utama + Wakil Direktur Utama (setara)

| Modul | Detail |
|---|---|
| Overview Dashboard | Real-time snapshot: People, Teknologi, Sales, Finance, Outsource |
| P&L & EBITDA | Interaktif, filter periode, comparison, trend 12 bulan, breakdown per revenue stream |
| AI Executive Summary | Auto-generate awal bulan, narrative + chart, chat interaktif real-time |
| People Analytics | Bell curve rating, top/under performers, trend per dept |
| Project Health | At-risk projects, utilization rate, delivery status |

---

## 10. Fitur Global (Semua Karyawan)

**Self-service (semua level):**
- Submit cuti (Tahunan, Sakit, Melahirkan, Duka, Menikah) — approval 2 lapis
- Submit reimbursement — transfer terpisah dari payroll
- Request pengunduran diri (notice 30 hari)
- Lihat slip gaji & riwayat payroll (semua history sejak bergabung)
- Lihat history rating bulanan
- Lihat notifikasi (in-app)
- Lihat org chart seluruh perusahaan
- Lihat info perusahaan (handbook, SOP, kebijakan)
- Lihat berita & event (global + dept)

**Level tertentu (Manager ke atas):**
- Request hiring / replacement / layoff
- Request pengadaan barang
- Buat broadcast (rich text + gambar + file, targeted per dept/level/global)
- Buat event (RSVP + reminder otomatis)
- Generate Executive Summary dept

---

## 11. Employee Lifecycle

```
HIRE → ONBOARD → PROBATION → AKTIF → EXIT → ALUMNI
```

### Probation
- 3 bulan, penilaian khusus
- Bisa diperpanjang 1x (max)
- Hasil: Lulus → Active | Tidak lulus → Terminated

### OKR Cycle
- Set per kuartal (Jan/Apr/Jul/Okt) oleh atasan langsung
- Evaluasi bulanan, threshold SP tetap berlaku

### Mutasi Antar Dept
- Operation initiate atas arahan manajemen
- Penilaian lama tetap di history, mulai fresh di dept baru

### Promosi
- Operation proses atas arahan GM/C-Level
- Sistem suggest range gaji per level
- Efektif per tanggal yang ditentukan saat input

### Resign
- Notice period 30 hari
- Atasan acknowledge, Operation proses
- Checklist offboarding = sama dengan layoff
- Akses portal langsung dicabut saat status Resigned

### Layoff
- Dipicu dari request dept atau SP3
- Approval 2 lapis wajib
- Akses langsung dicabut saat Terminated

### Cuti Panjang
- Penilaian di-skip selama cuti panjang
- Project assignment di-hold, digantikan member lain

### PKWT vs PKWTT
- Keduanya ada di IDEA
- Alert H-30 & H-7 ke atasan langsung + Operation

---

## 12. Payroll Cycle

**Komponen:**
```
PENGHASILAN: Gaji Pokok + Tunjangan Tetap + Lembur + Bonus/Komisi + Tunjangan variabel
POTONGAN: BPJS Kesehatan (1%) + BPJS Ketenagakerjaan (2%) + PPh21 (manual) + Potongan custom
TAKE HOME PAY = Penghasilan - Potongan
```

**Timeline per bulan:**
```
Sepanjang bulan   → cuti, lembur (input Operation), komisi Sales otomatis
H-5 gajian        → Operation rekap & submit ke Finance
H-3 gajian        → Finance hitung, PPh21 manual, approval GM/C-Level
Tanggal gajian    → Slip gaji publish ke portal, notif karyawan
```

**Aturan khusus:**
- Tanggal gajian dikonfigurasi per periode
- Reimbursement = transfer terpisah (bukan via payroll)
- Gaji prorata jika resign/terminated di tengah bulan
- THR = configurable, checklist dari variable gaji, transfer terpisah
- Payroll ditahan jika atasan belum submit penilaian

---

## 13. Project Lifecycle

```
LEAD → PROPOSAL → KICK-OFF → DELIVERY → CLOSING & INVOICE
```

**3 Tipe Project:**
| Tipe | Origin | Finance |
|---|---|---|
| Client Project | Closed Won dari Sales | Revenue |
| Internal Project | Request GM/C-Level, approval Direktur | Cost (OPEX/CAPEX) |
| R&D (sub-tipe Internal) | Sama dengan Internal | Cost, kategori terpisah |

**Closing Authority:**
- Normal: PM submit → GM/C-Level approve → Completed
- Exception: Direktur Utama bisa close langsung kapan saja (wajib input alasan)
- Status: DRAFT | ACTIVE | ON HOLD | COMPLETED | TERMINATED

**Invoice per Termin:**
- Setup saat kick-off, notif otomatis ke Finance saat milestone tercapai
- Track status: Sent → Partial → Paid
- Outstanding termin masuk dashboard Executive

---

## 14. Outsource Lifecycle

```
PLACEMENT → ONBOARDING CLIENT → AKTIF (Timesheet + BA) → RENEWAL → ENDING
```

**Billing per client (dikonfigurasi):**
- Tipe A: Flat per bulan (nominal tetap)
- Tipe B: Per hari kerja aktual (rate × hari hadir dari timesheet)

**Timesheet Flow:**
```
Karyawan input → Submit ke Operation → Operation verifikasi & approve → Generate BA
```

**BA Digital Signature:**
```
BA auto-generate dari timesheet (PDF) → IDEA sign digital → Link dikirim ke PIC client
→ Client buka via token unik (tanpa login) → Client tanda tangan → BA status: Signed
→ Notif Finance → Proses invoice
```

**Alert:** H-30 & H-7 sebelum kontrak berakhir ke atasan langsung + Operation

---

## 15. Data Migration

| Aspek | Keputusan |
|---|---|
| Payroll historical | Semua history sejak masing-masing bergabung |
| Method | Hybrid: bulk import (karyawan, org, client) + manual (project, leads) |
| Project import | Manual + bisa import dari Jira (project aktif only) |
| Parallel run | Tidak ada, langsung cutover |
| Sistem lama | Read-only 30 hari post go-live, lalu dimatikan |

---

## 15.1 Development Roadmap

Roadmap lengkap timeline pengembangan dari kickoff sampai go-live ada di file terpisah:

📅 **`IDEA_Development_Roadmap.md`** — Master plan:
- Kickoff: **1 Jun 2026**
- Go-live: **5 Jul 2027** (14 bulan total)
- 4 phase × 12 sub-milestone × 4 phase gate
- Team: 10–12 orang (Tech Lead, 3 BE, 3 FE, AI, DevOps, QA, PM, Designer)
- Velocity target: 40–45 pts/sprint (2-week sprint, total ~28 sprint)
- Risk register: 10 items dengan mitigasi
- Critical path: TSK-003 (RBAC) → TSK-013 (Employee Master) → TSK-046 (Payroll) → TSK-062 (Project CRUD)
- Success metrics: on-time, on-budget, adoption ≥95%, audit coverage 100%

**Phase summary:**

| Phase | Window | Tasks | Points | Sprints |
|---|---|---:|---:|---:|
| PH1 Foundation | 8 Jun – 27 Sep 2026 | 66 | 370 | 8 |
| PH2 Core Operations | 28 Sep 2026 – 17 Jan 2027 | 64 | 382 | 8 |
| PH3 Growth | 18 Jan – 11 Apr 2027 | 44 | 237 | 6 |
| PH4 Intelligence | 12 Apr – 6 Jun 2027 | 26 | 201 | 4 |
| UAT + Go-Live + Hypercare | 7 Jun – 2 Aug 2027 | — | — | 2 |

---

## 16. Tech Stack

| Layer | Teknologi |
|---|---|
| Frontend | React + TypeScript, Ant Design, Zustand + React Query |
| Backend | FastAPI (Python), Celery + Redis |
| AI | Claude API (Anthropic) — claude-sonnet-4-20250514 |
| Database | PostgreSQL 16, SQLAlchemy 2.0 + Alembic |
| Storage | MinIO (self-hosted S3) |
| PDF | WeasyPrint + Jinja2 |
| Infrastructure | Docker + Docker Compose, Nginx, Let's Encrypt |
| Monitoring | Prometheus + Grafana |

---

## 17. Design System (UI)

**Font:** Plus Jakarta Sans + JetBrains Mono (untuk angka)

**Color Variables:**
```
--blue:   #007AFF    --bl: #E8F1FF
--green:  #30D158    --gl: #E5F9EC
--orange: #FF9F0A    --ol: #FFF3E0
--red:    #FF453A    --rl: #FFECEB
--purple: #BF5AF2    --pl: #F5EEFE
--teal:   #32D2F2    --tl: #E5F9FE
```

**Border Radius:**
```
--r:  16px (cards)
--rm: 12px (medium)
--rs: 8px  (small)
```

**Theme:** Apple-inspired, light mode, desktop-first, sidebar navigation

---

## 18. Gap Alignment — Status & Resolusi

**Update 2026-05-26:** Hasil review konsistensi v2 (lihat sec.21).

| # | Gap Original | Status | Resolusi |
|---|---|---|---|
| 1 | Email vs NIK | ✅ RESOLVED | **NIK** ditetapkan sebagai login identifier (lihat Sec 1). Email tetap di profil, BUKAN untuk login. ERD perlu update kolom `login_identifier = NIK`. |
| 2 | Komisi Sales → Payroll variable | ✅ RESOLVED | Aturan ditambah di Sec 7 ("Komisi → Payroll"). UI mockup `IDEA_SalesLeads.html` di-update dengan panel commission. Task baru ditambah di xlsx. |
| 3 | Invoice termin → Notif Finance | ✅ RESOLVED | TSK-137 sudah cover backend. UI mockup `IDEA_ProjectManagement.html` di-update dengan panel "Termin & Invoice". |
| 4 | Wakil Direktur Utama tidak ter-elaborasi | ✅ RESOLVED | Detail permission ditambah di Sec 2. User story US-EX-005 ditambah. |
| 5 | SP-O (SP Outsource) tidak terdokumentasi | ✅ RESOLVED | Sub-section SP-O ditambah di Sec 5. Task TSK-110 duplikat dihapus (kept TSK-148). |
| 6 | Promosi/Mutasi/PKWT tanpa user story | ✅ RESOLVED | US-OP-012 (Promosi), US-OP-013 (Mutasi), US-OP-014 (PKWT Alert) ditambah. |
| 7 | AI Action Items tanpa user story | ✅ RESOLVED | US-SM-005 ditambah. |
| 8 | Assessment flag warna tidak tampak di UI | ✅ RESOLVED | Mockup `IDEA_AssessmentForm.html` di-update dengan visual flag kuning/oranye/merah. |
| 9 | Negative case missing untuk 4 story | ✅ RESOLVED | NC-OP-011, NC-TK-007, NC-GL-007, NC-GL-008 ditambah. |
| 10 | Negative case missing untuk US-EX-005 (Wakil Direktur) | ✅ RESOLVED | NC-EX-005 ditambah dengan 7 case (konflik simultan, audit persona, delegasi, escalation). |

---

## 19. Progress Halaman UI

**Total: 37 halaman fitur selesai / 37 halaman fitur target — 🎉 100% COMPLETE**
*Catatan:* `IDEA_ERD.html` adalah dokumentasi ERD (diagram), bukan halaman fitur — tidak masuk hitungan progress.

### Selesai (37 halaman fitur):
- Auth: Login, Onboarding Gate, Employee Dashboard
- Penilaian: Assessment Config, Assessment Form, Report per Karyawan
- Org: Org Chart
- Operation: Hiring Module, Layoff & Resign, Surat Peringatan, Outsource Management, Payroll Processing
- Sales: Leads Funnel, Proposal Management, Sales Report & Target
- Finance: Laporan Keuangan, Input Transaksi & CoA, Pengadaan Barang
- Executive: Executive Dashboard, P&L & EBITDA, AI Summary, **People Analytics** ✨, **Project Health Dashboard** ✨
- Global: Cuti & Reimburse, Project Management, **Notifikasi** ✨, **Profil Saya** ✨, **Slip Gaji & Riwayat Payroll** ✨, **Pengumuman & Broadcast** ✨, **Event Perusahaan** ✨, **Info Perusahaan** ✨, **Riwayat Penilaian (self-view)** ✨, **Onboarding Karyawan (employee-side)** ✨
- Operation: **Assignment Role & Lifecycle** ✨ (Assign + Promosi + Mutasi + PKWT/PKWTT)
- Teknologi: **Employee Management Teknologi** ✨ (List + Workload + 9-Box Matrix), **Dokumentasi Teknis per Project** ✨
- Finance: **Invoice & AR Tracking** ✨ (Aging buckets + alert H+7/H+14/H+30)

### Belum Dibuat: 🎉 NONE — Semua 37 halaman fitur sudah dibuat!

---

## 20. Database ERD — 42 Tables, 7 Domains

**Domain 1: Identity & Auth**
users, user_roles, role_permissions, audit_logs

**Domain 2: Organization**
departments, positions, employees, employee_contracts, org_changes

**Domain 3: Assessment & Performance**
assessment_configs, assessment_items, assessment_periods, assessments, okr_objectives, okr_key_results, warning_letters

**Domain 4: Project & Work**
projects, project_members, project_milestones, project_tasks, project_documents, project_invoices

**Domain 5: Outsource**
clients, outsource_placements, timesheets, timesheet_items, berita_acara, **client_complaints**, **warning_letters_outsource** *(SP-O)*

**Domain 6: HR & Payroll**
leave_types, leave_requests, payroll_configs, payroll_periods, payroll_components, payroll_slips, reimbursements, procurement_requests, vendors, **work_calendars**, **holidays**

**Domain 7: Sales**
leads, lead_activities, proposals, proposal_items, sales_targets, **sales_action_items** *(AI-generated)*, **sales_commissions** *(link ke payroll_components)*

---

## 21. Changelog — Konsistensi v2 (2026-05-26)

Hasil review konsistensi komprehensif, 10 temuan ter-resolve.

### Perubahan Struktural
- **Login Identifier:** NIK dipilih sebagai single source of truth. ERD perlu rename `email` field role menjadi profil-only.
- **Wakil Direktur Utama:** Naik dari catatan menjadi role RBAC eksplisit dengan permission detail (Sec 2).
- **SP-O:** Sub-section baru di Sec 5. Flow terpisah dari SP internal karena trigger berbeda (complaint client vs score penilaian).
- **Komisi → Payroll:** Auto-flow rule ditambah di Sec 7 untuk sales PIC commission (bukan referral).

### Modul Baru Terdokumentasi
- Client Complaint Management (di Sec 5)
- Work Calendar Management (sebelumnya hanya di TSK-026, sekarang resmi)
- Promosi & Mutasi (sebelumnya hanya di Sec 11 lifecycle, sekarang juga modul Operation)
- PKWT/PKWTT Tracking & Alert (modul Operation)

### Dokumen yang Di-update
| Dokumen | Perubahan |
|---|---|
| `knowledge.md` | Sec 1, 2, 5, 7, 18, 19, 20 di-update + Sec 21 baru |
| `IDEA_User_Stories.docx` | +5 stories: US-EX-005, US-OP-012, US-OP-013, US-OP-014, US-SM-005 |
| `IDEA_Negative_Cases.docx` | +5 grup: NC-OP-011, NC-TK-007, NC-GL-007, NC-GL-008, NC-EX-005 |
| `IDEA_Task_Management.xlsx` | TSK-110 dihapus (duplikat TSK-148), tambah TSK baru untuk auto-flow komisi & Wakil Direktur RBAC |
| `GUI html/IDEA_ProjectManagement.html` | Tambah panel "Termin & Invoice" |
| `GUI html/IDEA_SalesLeads.html` | Tambah panel "Commission on Closed Won" |
| `GUI html/IDEA_AssessmentForm.html` | Tambah visual flag warna (kuning/oranye/merah) |
| `GUI html/IDEA_surat_peringatan.html` | Tambah section SP-O (Outsource SP) |
| `GUI html/IDEA_Notifikasi.html` ✨ NEW | Sprint A: Halaman notifikasi full page (kategori filter, group by date, mark read/unread, badge counter) |
| `GUI html/IDEA_AssignmentRole.html` ✨ NEW | Sprint A: 4 tab (Assign Role, Promosi US-OP-012, Mutasi US-OP-013, Kontrak PKWT/PKWTT US-OP-014) + audit trail + persona Wakil Direktur |
| `GUI html/IDEA_ProfilSaya.html` ✨ NEW | Sprint A: Self-service profile (info pribadi, kepegawaian, project aktif, saldo cuti, slip gaji terakhir, rating mini, org position, danger zone) |
| `GUI html/IDEA_SlipGaji.html` ✨ NEW | Sprint B: Slip gaji + riwayat payroll lengkap (history pane semua bulan, slip paper detail dengan komponen+potongan+THP, YTD stats, trend bar 12 bulan) |
| `GUI html/IDEA_EmployeeMgmtTK.html` ✨ NEW | Sprint B: Employee Mgmt Teknologi (US-TK-007) — list view dengan alokasi/skill/rating, workload view dengan over-allocation alert, 9-Box matrix performance×allocation |
| `GUI html/IDEA_InvoiceAR.html` ✨ NEW | Sprint B: Invoice & AR Tracking (US-FN-006) — AR hero summary, aging buckets 5-tier, table invoice dengan status flow, alert schedule H+7/H+14/H+30, top client by AR |
| `GUI html/IDEA_PeopleAnalytics.html` ✨ NEW | Sprint C: Executive People Analytics — bell curve rating distribution, top/under performers, dept comparison, hire vs resign trend 12 bulan, rating heatmap dept×level, AI insight. Dark sidebar untuk Executive. |
| `GUI html/IDEA_ProjectHealth.html` ✨ NEW | Sprint C: Executive Project Health — at-risk hero alert, project table dengan progress vs timeline, donut tipe project (Client/Internal/R&D), Gantt mini timeline Q2, outstanding termin linked ke Invoice, revenue forecast Q1–Q4, AI strategic insight. |
| `GUI html/IDEA_Pengumuman.html` ✨ NEW | Sprint D: Broadcast feed (pinned, RSVP, dept-specific) + composer dengan target audience chips (Global/Dept/Level), rich text toolbar, preview panel |
| `GUI html/IDEA_Event.html` ✨ NEW | Sprint D: Event list (cards dengan date badge) + calendar view (month grid). RSVP buttons, attendee stack, event types (All-Hands/Tech Talk/Training/Town Hall/Sosial/Offsite) |
| `GUI html/IDEA_InfoPerusahaan.html` ✨ NEW | Sprint D: CMS sederhana dengan category sidebar (Vision/Handbook/SOP/Kebijakan/Compliance/Template/Training) + featured docs, doc grid dengan multi-format (PDF/Word/Excel/MD/Video) |
| `GUI html/IDEA_RiwayatPenilaian.html` ✨ NEW | Sprint D: Self-view rating dengan hero score circle, **SVG line chart 12-bulan** (OKR+Weighted+Final), breakdown Mei dengan formula, OKR Q2 progress (3 of 4 on-track), peer comparison anonim |
| `GUI html/IDEA_DokumentasiTeknis.html` ✨ NEW | Sprint D: Per-project tech docs (US-TK-003) — folder tree (00-Overview, 01-Architecture, 02-API, dst), file grid dengan version chips, project switcher, access control banner (member-only) |
| `GUI html/IDEA_OnboardingKaryawan.html` ✨ NEW | Sprint D: Employee-side onboarding (US-OP-003) — welcome hero gradient, 65% progress circle, checklist 20 task (Administratif/Asset/Learning/Meet Team/First Contribution), welcome messages dari leadership, FAQ, quick links |

### Total Inventaris Setelah Update
- User Stories: **46** (semula 41)
- Negative Cases: **45 grup, ~216 case** (semula 40 grup, 185)
- Task xlsx: **~195 tasks** (semula 192, -1 duplikat +beberapa tambahan)
- ERD Tables: **47** (semula 42, +5 new tables)

