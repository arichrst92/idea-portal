# IDEA Internal Portal — Development Roadmap
**PT. Solusi Inovasi Bangsa (IDE Asia)**
**Versi 1.0 · 2026-05-26**

---

## Executive Summary

Roadmap pengembangan IDEA Internal Portal dari **kickoff 1 Juni 2026** sampai **go-live target Q3 2027** (~14–18 bulan). Cakupan: **200 task aktif** dalam **25 epic**, terdistribusi di **4 fase** dengan **12 sub-milestone** dan **4 phase gate**.

**Total effort:** 1.190 story points · ~28–34 sprint (2 minggu/sprint) · velocity target 25–35 pts/sprint setelah ramp-up.

**⚡ Solo dev + AI setup:** Ari Christian sebagai sole developer dengan Claude sebagai AI pair programmer. Velocity lebih rendah dari tim besar tapi dapat di-boost dengan AI untuk boilerplate, testing, dan documentation.

```
1 Jun 2026  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  5 Jul 2027 (ambitious)
            │PH1 16wk│  PH2 16wk  │  PH3 12wk │PH4 8wk│UAT│GO│            atau Q3-Q4 2027 (realistic)
            │  370pt │   382pt    │   237pt   │ 201pt │   │  │
            └────────┴────────────┴───────────┴───────┴───┴──┘
                Foundation     Core Ops    Growth   AI    UAT
```

---

## 1. Team Composition

**Solo dev + AI pair programmer setup:**

| Role | Pengisi | Catatan |
|---|---|---|
| **Product Owner + Tech Lead + Sole Developer** | **Ari Christian** (arichrst@ide.asia) | All roles dalam satu orang |
| **AI Pair Programmer** | **Claude** (Anthropic) | Code generation, review, testing, docs, debugging |

### Velocity Assumption — Solo + AI

| Phase | Solo Velocity | + Claude Assist | Effective |
|---|---:|---:|---:|
| Sprint 1–3 (Ramp-up) | 8–12 pts/sprint | +50% boost | 12–18 pts/sprint |
| Sprint 4–15 (Steady) | 12–18 pts/sprint | +60% boost | 20–30 pts/sprint |
| Sprint 16+ (Mature) | 15–20 pts/sprint | +70% boost | 25–35 pts/sprint |

**Kenapa Claude bisa boost velocity:**
- Boilerplate code (CRUD, validation, models) — Claude generate cepat
- Test scaffolding — Claude bikin pytest/jest skeleton
- Documentation — auto-write docstring, README updates
- Debugging — second pair of eyes untuk stack traces
- Refactoring — propose dan apply refactor patterns

**Yang tetap butuh waktu Ari fokus:**
- Architectural decisions (Claude propose, Ari decide)
- Complex business logic (Claude assist tapi Ari review penuh)
- Data migration design (high-stakes, careful)
- Production deployment & cutover
- Stakeholder communication

### Cost Estimate (Solo Setup)

| Item | Estimate |
|---|---|
| Ari Christian (internal cost) | Salary continued — tidak ada extra cost |
| Claude API (Anthropic) | ~$20–50/month subscription untuk Claude Pro/Max + occasional API for production AI features |
| Cloud infra (dev+staging+prod) | ~Rp 2–5 jt/bulan (Hetzner/Contabo/GCP startup credit) |
| GitHub | Free (private repo OK) |
| Domain + SSL | Sudah ada (ide.asia) |
| **Total cash cost** | **~Rp 100–200 jt over 14 bulan** (jauh lebih murah dari tim) |

### Trade-off Solo+AI vs Tim

| Aspek | Solo+AI | Tim 10 orang |
|---|---|---|
| Speed | Slower (1 person bottleneck) | Faster (parallelize) |
| Cost | ~Rp 100–200 jt | ~Rp 21–28 M |
| Consistency | Tinggi (1 brain) | Perlu coordination |
| Risk | Bus factor = 1 (kritis!) | Lebih resilient |
| Stakeholder mgmt | Ari sendiri | PM dedicated |
| Scope mgmt | Critical — harus disiplin | Lebih fleksibel |

**🚨 Mitigation untuk bus factor risk:** Heavy documentation di knowledge.md + commit history yang clean + recorded decisions di CLAUDE.md.

---

## 2. Sprint Cadence (Solo + AI Adjusted)

- **Sprint length:** 2 minggu (Senin–Jumat × 2 minggu)
- **Sprint 0 (Kickoff):** 1 minggu untuk environment setup
- **Velocity target (Solo + Claude):**
  - Sprint 1–3: **12–18 pts** (ramp-up, learning curve)
  - Sprint 4–15: **20–30 pts** (steady state, pair-programming flow established)
  - Sprint 16+: **25–35 pts** (mature, patterns reusable)
- **Sprint ritual untuk solo dev:**
  - **Planning** Senin pagi (1 jam, dengan Claude untuk break-down task)
  - **Daily checkpoint** ke Claude (5 menit pagi, review progress)
  - **Mid-sprint demo to self** Kamis week 1 (validate progress, adjust)
  - **Sprint review + retro** Jumat week 2 (1 jam, self-review)
  - **Commit + push** setiap selesai task — jangan tunggu akhir sprint

**Discipline penting untuk solo dev:**
- Definisi "done" yang strict: test pass + push ke remote + dokumentasi update
- Time-box per task — kalau stuck >2 jam, switch context atau minta Claude review
- Daily git push (minimal) — jangan biarkan WIP menumpuk lokal

---

## 3. Timeline Master (Dua Skenario)

### Skenario A: Ambitious (target asal, jika velocity tinggi konsisten)

Asumsi: rata-rata 30 pts/sprint solid throughout, no major slip.

| Fase | Tanggal | Durasi | Tasks | Points | Sprints |
|---|---|---:|---:|---:|---:|
| **Kickoff (Sprint 0)** | 1–7 Jun 2026 | 1 minggu | — | — | 0 |
| **PH1 — Foundation** | 8 Jun – 27 Sep 2026 | 16 minggu | 66 | 370 | 8 |
| **PH2 — Core Operations** | 28 Sep 2026 – 17 Jan 2027 | 16 minggu | 64 | 382 | 8 |
| **PH3 — Growth** | 18 Jan – 11 Apr 2027 | 12 minggu | 44 | 237 | 6 |
| **PH4 — Intelligence** | 12 Apr – 6 Jun 2027 | 8 minggu | 26 | 201 | 4 |
| **Pre-Launch (UAT + Bugfix)** | 7 Jun – 4 Jul 2027 | 4 minggu | — | — | 2 |
| **Go-Live Weekend** | 4–5 Jul 2027 | — | — | — | — |
| **Hypercare** | 6 Jul – 2 Aug 2027 | 4 minggu | — | — | — |

**Total Skenario A:** ~14 bulan. **Risiko:** sangat aggressive untuk solo dev, ada slip risk tinggi.

### Skenario B: Realistic (target rekomendasi)

Asumsi: rata-rata 22 pts/sprint, ada buffer untuk holiday + slip recovery + scope adjustment.

| Fase | Tanggal | Durasi | Tasks | Points | Sprints |
|---|---|---:|---:|---:|---:|
| **Kickoff (Sprint 0)** | 1–7 Jun 2026 | 1 minggu | — | — | 0 |
| **PH1 — Foundation** | 8 Jun – 27 Dec 2026 | 24 minggu | 66 | 370 | 12 |
| **PH2 — Core Operations** | 28 Dec 2026 – 16 May 2027 | 20 minggu | 64 | 382 | 10 |
| **PH3 — Growth** | 17 May – 8 Aug 2027 | 12 minggu | 44 | 237 | 6 |
| **PH4 — Intelligence** | 9 Aug – 3 Oct 2027 | 8 minggu | 26 | 201 | 4 |
| **Pre-Launch (UAT + Bugfix)** | 4 Oct – 31 Oct 2027 | 4 minggu | — | — | 2 |
| **Go-Live Weekend** | 30–31 Oct 2027 | — | — | — | — |
| **Hypercare** | 1 Nov – 28 Nov 2027 | 4 minggu | — | — | — |

**Total Skenario B:** ~18 bulan. **Risiko:** lebih achievable, masih dalam window 2027.

### Skenario Rekomendasi: B (Realistic)

Pilih **Skenario B** sebagai default, evaluate ulang setelah PH1 selesai. Jika velocity ternyata lebih tinggi, accelerate ke Skenario A.

**Total work tetap:** 200 tasks · 1.190 points · 28–34 sprints (incl. UAT)

### MVP Strategy — Opsi De-Scope

Jika timeline harus dipendekkan, pertimbangkan MVP cut:

- **MVP-1 (12 bulan):** PH1 + PH2 only = 130 task / 752 pts = ~26 sprints
  - Drop dulu: PH3 Sales features + PH4 AI features
  - Go-live dengan core ops, tambahin growth+AI di v1.1
- **MVP-2 (10 bulan):** PH1 + EP-07 (Project Mgmt) + EP-08 (Assessment) + EP-09 (Finance) = ~100 task / 600 pts
  - Skip outsource, sales, AI sampai v1.1

Diskusikan dengan stakeholder kalau timeline jadi blocker.

---

## 4. Milestone Detail

### Sprint 0 — Kickoff & Setup
**1 Jun – 7 Jun 2026 · 1 minggu**

| Aspek | Detail |
|---|---|
| **Goal** | Tim siap & environment running |
| **Deliverable** | Repo, CI/CD pipeline, dev/staging env, comm channels, sprint board |
| **Acceptance** | Tim bisa run `docker compose up` lokal & deploy ke staging |
| **Risk** | Onboarding lambat → buffer 3 hari included |

**Checklist:**
- Repo GitHub IDE Asia + branch protection rules
- Setup Docker Compose dev environment (PostgreSQL 16, Redis, MinIO, Celery)
- CI/CD pipeline (GitHub Actions → staging deploy)
- Staging environment di GCP/AWS provisioned
- Slack channel + Jira project + tech wiki
- All-hands kickoff meeting + technical onboarding session
- Sprint 1 backlog refinement & estimation

---

### 🏗️ PH1 — FOUNDATION
**8 Jun – 27 Sep 2026 · 16 minggu · 8 sprints · 66 tasks · 370 pts**

> Tujuan utama: **identity layer + people data + payroll basics** harus solid sebelum modul lain dibangun di atasnya.

#### M1.1 — Authentication & Authorization
**8 Jun – 5 Jul 2026 · 4 minggu · 2 sprints · 13 tasks · 76 pts**

| Aspek | Detail |
|---|---|
| **Tasks** | TSK-001 s/d TSK-012 + **TSK-193** (Wakil Direktur RBAC) |
| **Epic** | EP-01 |
| **Deliverable** | Single login portal.ide.asia · JWT · RBAC level 1–6 · Wakil Direktur sebagai role terpisah |
| **Tim utama** | 2 BE + 1 FE + Tech Lead |
| **Critical** | RBAC engine harus benar — semua modul lain tergantung sini |
| **Risiko** | Wakil Direktur persona di audit log harus eksplisit (NC-EX-005 mandate) |

#### M1.2 — Master Data & Organization
**6 Jul – 9 Aug 2026 · 5 minggu · 2.5 sprints · 19 tasks · 101 pts**

| Aspek | Detail |
|---|---|
| **Tasks** | TSK-013 s/d TSK-028 + **TSK-197** (Promotion UI) + **TSK-198** (Mutation UI) + **TSK-199** (PKWT UI) |
| **Epic** | EP-02 |
| **Deliverable** | Employee master · Org tree · Role assignment · Promotion/Mutation flow · PKWT alert |
| **Tim utama** | 2 BE + 2 FE |
| **Acceptance** | Bisa import 150 karyawan via Excel + assignment role works |
| **Risiko** | Data migration dari sistem lama — siapkan template Excel awal |

#### M1.3 — Hiring & Onboarding
**10 Aug – 6 Sep 2026 · 4 minggu · 2 sprints · 17 tasks · 94 pts**

| Aspek | Detail |
|---|---|
| **Tasks** | TSK-029 s/d TSK-045 |
| **Epic** | EP-03, EP-04 |
| **Deliverable** | Internal job board · 2-layer approval engine · Offering letter · Onboarding checklist · Welcome page |
| **Tim utama** | 2 BE + 2 FE |
| **Acceptance** | End-to-end: Manager request hiring → approved → kandidat di-hired → onboarding checklist auto-create |
| **Catatan** | 17 Agt 2026 = HUT RI (libur 1 hari), buffer minor |

#### M1.4 — Payroll Foundation + Notifikasi
**7 Sep – 27 Sep 2026 · 3 minggu · 1.5 sprints · 17 tasks · 99 pts**

| Aspek | Detail |
|---|---|
| **Tasks** | TSK-046 s/d TSK-061 |
| **Epic** | EP-05, EP-06 |
| **Deliverable** | Payroll calc engine (fixed+variable+potongan+BPJS+PPh21) · Slip gaji PDF · In-app notification system · Alert rules (PKWT H-30/H-7) |
| **Tim utama** | 3 BE + 1 FE |
| **Acceptance** | Run payroll Sep 2026 untuk 10 dummy karyawan tanpa error · notif terkirim ke semua approver test |
| **Risiko** | Multi-currency edge case — pastikan IDR sebagai default |

#### 🚪 PH1 GATE — Foundation Demo
**28 Sep 2026**

**Acceptance checklist (semua harus PASS):**
- [ ] Login dengan NIK + JWT (US-OP-001 happy path)
- [ ] 6 level RBAC enforced di API level
- [ ] Wakil Direktur Utama role terpisah dengan audit eksplisit
- [ ] Bulk import 150 karyawan via Excel succeed
- [ ] Hiring flow end-to-end (2-layer approval)
- [ ] Onboarding checklist auto-create on hired
- [ ] Payroll dummy run untuk 10 karyawan = 10 slip gaji PDF tergenerate
- [ ] Notifikasi PKWT H-30 terkirim untuk 1 test case
- [ ] **Stakeholder sign-off:** Direktur Utama, GM Operation, CTO

**Jika ada gap:** alokasikan sprint buffer di PH2 awal sebelum lanjut.

---

### ⚙️ PH2 — CORE OPERATIONS
**28 Sep 2026 – 17 Jan 2027 · 16 minggu · 8 sprints · 64 tasks · 382 pts**

> Core daily operations untuk semua departemen + finance backbone.

#### M2.1 — Project Management + Assessment & OKR
**28 Sep – 8 Nov 2026 · 6 minggu · 3 sprints · 25 tasks · 157 pts**

| Aspek | Detail |
|---|---|
| **Tasks** | TSK-062 s/d TSK-086 |
| **Epic** | EP-07, EP-08 |
| **Deliverable** | Project CRUD (Client/Internal/R&D types) · Kanban + Gantt · OKR framework · Monthly assessment · Threshold flag (kuning/oranye/SP trigger) |
| **Tim utama** | 2 BE + 3 FE (UI-heavy phase) |
| **Acceptance** | PM bisa setup project + assign team + tracking · GM bisa setup OKR Q1 untuk dept Teknologi |
| **Catatan** | Lebaran/Idul Fitri 2026 = Q1 2027, tidak conflict |

#### M2.2 — Finance & Accounting
**9 Nov – 6 Dec 2026 · 4 minggu · 2 sprints · 14 tasks · 87 pts**

| Aspek | Detail |
|---|---|
| **Tasks** | TSK-087 s/d TSK-099 + **TSK-200** (Invoice Termin UI) |
| **Epic** | EP-09 |
| **Deliverable** | CoA · Daily transaction (accrual) · Multi-currency engine · Financial reports (P&L, Neraca, Cash Flow) · Invoice tracking dengan auto-alert · Termin per project |
| **Tim utama** | 2 BE + 1 FE |
| **Acceptance** | Finance bisa input transaksi dummy seluruh CoA · generate P&L untuk Nov 2026 |
| **Critical** | PKP/PPN 11% calc benar · multi-currency: nominal asli + kurs + IDR equiv tersimpan |

#### M2.3 — Outsource + Leave + Reimburse + Procurement
**7 Dec 2026 – 17 Jan 2027 · 6 minggu (incl holiday) · 3 sprints · 25 tasks · 138 pts**

| Aspek | Detail |
|---|---|
| **Tasks** | TSK-100 s/d TSK-124 + **TSK-196** (Client Complaint Logging) |
| **Epic** | EP-10, EP-11, EP-12, EP-13 |
| **Deliverable** | Outsource placement · Timesheet flow · Leave management · Reimbursement · Procurement · Client complaint logging (feeds SP-O di PH3) |
| **Tim utama** | 2 BE + 2 FE |
| **Acceptance** | Outsource bisa input timesheet bulanan + BA auto-generate · Karyawan bisa submit cuti + 2-layer approval |
| **Catatan** | Libur Natal (25-26 Dec) + Tahun Baru (1 Jan) = 1 minggu effective off, sudah include di buffer |

#### 🚪 PH2 GATE — Core Operations Demo
**18 Jan 2027**

**Acceptance checklist:**
- [ ] Project lifecycle: Lead → Kick-off → Delivery → Closing
- [ ] Penilaian bulanan run untuk 1 dept Teknologi penuh
- [ ] Threshold flag: kuning→oranye→merah auto-detected
- [ ] Multi-currency invoice: USD + IDR with kurs tersimpan
- [ ] Termin notif: milestone tercapai → Finance dapat notif otomatis
- [ ] Outsource: 1 placement timesheet → BA → invoice cycle complete
- [ ] Cuti & reimbursement bisa di-submit + approved end-to-end
- [ ] **Stakeholder sign-off:** GM Finance, GM Operation, CTO

---

### 📈 PH3 — GROWTH
**18 Jan – 11 Apr 2027 · 12 minggu · 6 sprints · 44 tasks · 237 pts**

> Sales suite + offboarding + executive portal — fokus pada growth & insight.

#### M3.1 — Sales Suite
**18 Jan – 21 Feb 2027 · 5 minggu · 2.5 sprints · 20 tasks · 112 pts**

| Aspek | Detail |
|---|---|
| **Tasks** | TSK-125 s/d TSK-143 + **TSK-194** (Komisi auto-flow to Payroll) |
| **Epic** | EP-14, EP-15, EP-16 |
| **Deliverable** | Lead funnel 6-stage · Proposal versioning · Target individu+tim · Win rate calc · **Auto-create variable payroll line on Closed Won** (untuk Sales PIC, bukan Direktur-driven) |
| **Tim utama** | 1 BE + 2 FE |
| **Acceptance** | Sales staff bisa kelola pipeline · Direktur-driven deal di-tag dan tidak generate komisi |

#### M3.2 — SP Automation + Resignation/Offboarding
**22 Feb – 14 Mar 2027 · 3 minggu · 1.5 sprints · 12 tasks · 53 pts**

| Aspek | Detail |
|---|---|
| **Tasks** | TSK-144 s/d TSK-149 + TSK-161 s/d TSK-166 |
| **Epic** | EP-17, EP-20 |
| **Deliverable** | SP1/SP2/SP3 sequence · **SP-O outsource (SP-O1/O2/O3)** · Resignation 30-hari notice · Offboarding checklist · Auto access revoke pada last working day |
| **Tim utama** | 2 BE + 1 FE |
| **Acceptance** | SP otomatis trigger dari score <60 × 3 bulan · SP-O dipicu client complaint · Resign full cycle |

#### M3.3 — Executive Portal + Broadcasting/Events
**15 Mar – 11 Apr 2027 · 4 minggu · 2 sprints · 12 tasks · 72 pts**

| Aspek | Detail |
|---|---|
| **Tasks** | TSK-150 s/d TSK-160 + **TSK-201** (Wakil Direktur Persona Display) |
| **Epic** | EP-18, EP-19 |
| **Deliverable** | Executive dashboard (overview/people/project/sales) · EBITDA · People Performance · Broadcast module · Event management |
| **Tim utama** | 1 BE + 2 FE (dashboard heavy) |
| **Acceptance** | Direktur Utama + Wakil Direktur bisa akses Executive Portal · persona name tampil di header & audit |
| **Catatan** | Idul Fitri ~9–10 Apr 2027 (tentative) = ~1 minggu efektif off, buffer included |

#### 🚪 PH3 GATE — Growth Demo
**12 Apr 2027**

**Acceptance checklist:**
- [ ] Sales lead funnel 6-stage berfungsi penuh
- [ ] Komisi Sales auto-flow ke payroll variable component
- [ ] SP otomatis trigger berdasarkan rating 3 bulan
- [ ] SP-O Outsource flow dari client complaint
- [ ] Executive Dashboard real-time dengan widget 5 area
- [ ] Wakil Direktur persona tampil eksplisit di audit + dashboard
- [ ] Broadcast multi-target audience (global/dept/level)
- [ ] **Stakeholder sign-off:** GM Sales, GM HR, Direktur Utama, Wakil Direktur Utama

---

### 🤖 PH4 — INTELLIGENCE
**12 Apr – 6 Jun 2027 · 8 minggu · 4 sprints · 26 tasks · 201 pts**

> AI features + data migration + final analytics — paling kompleks per-point ratio.

#### M4.1 — AI Features
**12 Apr – 9 May 2027 · 4 minggu · 2 sprints · 9 tasks · 68 pts**

| Aspek | Detail |
|---|---|
| **Tasks** | TSK-167 s/d TSK-170 + TSK-176 s/d TSK-180 + **TSK-195** (AI Sales Action UI) |
| **Epic** | EP-21, EP-23 |
| **Deliverable** | AI Sales Action Items (per lead per stage) · AI SP Draft Generator · AI Executive Summary (monthly, narrative + chart) · AI service fallback handling |
| **Tim utama** | 1 AI Engineer + 1 BE + 1 FE |
| **Tech** | Claude API (claude-sonnet-4-20250514) |
| **Risiko** | API cost — set per-month budget cap. Fallback graceful saat API down |

#### M4.2 — Digital Signature + Data Migration
**10 May – 30 May 2027 · 3 minggu · 1.5 sprints · 11 tasks · 86 pts**

| Aspek | Detail |
|---|---|
| **Tasks** | TSK-171 s/d TSK-175 + TSK-181 s/d TSK-186 |
| **Epic** | EP-22, EP-24 |
| **Deliverable** | BA digital signature (client token, no-login) · Bulk import Excel template · Validation engine · Payroll history import · Jira project import |
| **Tim utama** | 2 BE + 1 FE |
| **Acceptance** | Client bisa sign BA via secure link tanpa login · Bulk import 200 karyawan + payroll history 12 bulan succeed |

#### M4.3 — Analytics & Reporting
**31 May – 6 Jun 2027 · 1 minggu · 0.5 sprint · 6 tasks · 47 pts**

| Aspek | Detail |
|---|---|
| **Tasks** | TSK-187 s/d TSK-192 |
| **Epic** | EP-25 |
| **Deliverable** | Comprehensive Report Module · HR Analytics · Sales Analytics · Finance KPI widgets · System Audit Log · Scheduled Report Generation |
| **Tim utama** | 1 BE + 1 FE |
| **Acceptance** | Semua report bisa di-export PDF/Excel · scheduled report jalan otomatis di tanggal config |

#### 🚪 PH4 GATE — Intelligence Demo
**7 Jun 2027**

**Acceptance checklist:**
- [ ] AI Sales Action Items: 1-3 saran per lead, contextual
- [ ] AI Exec Summary: auto-generate awal bulan dengan narrative
- [ ] BA digital signature flow: client sign tanpa login via token
- [ ] Bulk import: 200 karyawan + history 12 bulan
- [ ] All reports exportable
- [ ] **Stakeholder sign-off:** All C-Level

---

### 🧪 Pre-Launch (UAT + Bug Fix)
**7 Jun – 4 Jul 2027 · 4 minggu**

| Minggu | Aktivitas |
|---|---|
| **W1 (7–13 Jun)** | UAT Cycle 1 — semua departemen test scenarios |
| **W2 (14–20 Jun)** | UAT findings triage + bug fix sprint |
| **W3 (21–27 Jun)** | Data migration dry-run + load testing |
| **W4 (28 Jun – 4 Jul)** | Training Operation/HR/Finance/Sales · final tuning · go-live readiness review |

**Go/No-Go Decision:** **2 Jul 2027 (Jumat)** — review semua criteria:
- [ ] 0 P0 bug, ≤3 P1 bug
- [ ] Data migration verified
- [ ] Training completed 100%
- [ ] Rollback plan ready
- [ ] Stakeholder go-ahead

---

### 🚀 Go-Live Weekend
**Sabtu, 4 Jul 2027 — Minggu, 5 Jul 2027**

**Saturday timeline:**
- 08:00 — Backup sistem lama (final snapshot)
- 09:00 — Begin migration cutover
- 12:00 — Migration complete, verification
- 14:00 — Production smoke test
- 16:00 — DNS switch portal.ide.asia → new system
- 18:00 — Monitoring intensive, on-call team standby

**Sunday timeline:**
- 09:00 — Final verification semua role
- 12:00 — Send announcement to semua karyawan
- 18:00 — Hypercare mode begin

**Sistem lama:** Read-only 30 hari (sampai 3 Aug 2027), kemudian dimatikan.

---

### 🛡️ Hypercare
**6 Jul – 2 Aug 2027 · 4 minggu**

| Aspek | Detail |
|---|---|
| **Mode** | High-frequency monitoring, bug triage <2 jam SLA |
| **Tim** | All-hands available (rotating on-call) |
| **Sistem lama** | Read-only mode, dimatikan 3 Aug 2027 |
| **Deliverable** | Hypercare report + lessons learned + handover ke maintenance team |

---

### 🏁 Project Closeout
**3 Aug 2027**

- Final report → Direksi
- Project retrospective (full team)
- Maintenance handover ke ongoing support team
- Documentation finalization
- Celebration!

---

## 5. Risk Register (Solo Dev Adjusted)

| # | Risk | Likelihood | Impact | Mitigasi |
|---|---|---|---|---|
| R1 | Velocity solo lebih rendah dari proyeksi | **High** | High | Skenario B sebagai default. Re-baseline setiap akhir phase. Siapkan MVP de-scope plan. |
| R2 | **Bus factor = 1 (Ari sakit/cuti)** | Medium | **Critical** | Heavy doc di knowledge.md + CLAUDE.md, frequent push ke git, Claude bisa resume context |
| R3 | Burnout solo dev di project panjang | **High** | High | Time-box sprint dengan disiplin, minimal 1 hari off/minggu, hindari weekend coding |
| R4 | Scope creep dari stakeholder request baru | High | Medium | Change request log, defer ke v1.1 (post go-live), say "no" lebih sering |
| R5 | RBAC engine bug ditemukan setelah PH1 | Medium | Critical | Heavy testing di M1.1, Claude review code, security checklist sebelum PH1 gate |
| R6 | Data migration dari sistem lama corrupt/incomplete | Medium | High | 2x dry-run (PH2 awal + Pre-launch), validation engine di TSK-182 |
| R7 | AI Claude API cost over budget (untuk production AI features) | Medium | Medium | Monthly cap di config, fallback graceful, monitor usage |
| R8 | Lebaran 2027 jatuh saat PH3 critical path | Medium | Medium | Buffer 1 minggu, hindari deploy seminggu sebelum/sesudah |
| R9 | Wakil Direktur audit log tidak eksplisit (NC-EX-005) | Low | Critical | CI test dedicated untuk audit_logs assertion, fail build jika generic "Direktur" muncul |
| R10 | Go-live weekend issue (cutover gagal) | Low | Critical | Rollback plan tested, sistem lama tetap running parallel 1 hari |
| R11 | **Mac Mini hardware fail / power loss** | Low | **Critical** | Daily push ke GitHub (sudah jadi konvensi), backup `.env` & `secrets/` di password manager |
| R12 | **GitHub repo loss / accidental force-push** | Low | High | Enable branch protection di main setelah Sprint 0, jangan force-push ke main |

---

## 6. Critical Path

Tasks yang **tidak boleh slip** karena banyak dependency:

```
TSK-001 (Login) → TSK-002 (JWT) → TSK-003 (RBAC Engine) → TSK-193 (Wakil Direktur RBAC)
                                                ↓
                                    TSK-013 (Employee Master) → TSK-015 (Org Tree)
                                                ↓
                                    Semua modul lain depend on these
```

**4 task paling kritis (CP):**
1. **TSK-003** Role-Based Access Control Engine (M1.1) — block 90% task lain
2. **TSK-013** Employee Master Data Module (M1.2) — block hiring/payroll/assessment
3. **TSK-046** Payroll Component Configuration (M1.4) — block payroll cycle
4. **TSK-062** Project CRUD & Configuration (M2.1) — block PM/Outsource/Finance reporting

Jika 1 dari 4 ini slip > 1 sprint, **escalate immediate** ke PM + Direktur Utama.

---

## 7. Success Metrics

### Project Delivery
- **On-time:** Go-live 4-5 Jul 2027 ±1 minggu
- **On-budget:** Total cost ≤ Rp 28 M
- **Quality:** 0 P0 bug 30 hari post go-live, ≤10 P1 bug

### Adoption (90 hari post go-live)
- **Login rate:** ≥95% karyawan login min. 1x/minggu
- **Self-service:** ≥80% cuti & reimburse submitted via portal (vs email)
- **Penilaian:** 100% manager submit penilaian bulanan on-time
- **Payroll:** 100% slip gaji terbit via portal (no email PDF)

### Business Impact (180 hari post)
- **Operational efficiency:** -50% waktu HR processing approval (target 2 menit dari 5 menit)
- **Visibility:** 100% project status visible to Direksi via Executive Portal
- **Compliance:** 100% audit log coverage untuk approval & financial transactions

---

## 8. Document Cross-References

| Source of Truth | Untuk |
|---|---|
| **`knowledge.md`** | Spec fungsional, aturan bisnis, design system |
| **`IDEA_Task_Management.xlsx`** | Task tracking (200 task), sprint planning |
| **`IDEA_User_Stories.docx`** | Acceptance criteria per fitur (46 stories) |
| **`IDEA_Negative_Cases.docx`** | Edge case + validation (45 grup) |
| **`GUI html/*.html`** | 37 UI mockup (visual reference) |
| **This file** | Timeline, milestone, gate criteria, risk |

---

## 9. Sign-off

**Prepared by:** Tech Lead + PM IDEA Portal
**Date:** 2026-05-26

| Role | Nama | Signature | Date |
|---|---|---|---|
| Direktur Utama | Rudi Atmadja | ____________ | _______ |
| Wakil Direktur Utama | Siti Hartono | ____________ | _______ |
| CTO | Indra Wijaya | ____________ | _______ |
| GM Operation | Reni Wahyuni | ____________ | _______ |
| GM Finance | Dewi Ratnasari | ____________ | _______ |
| Tech Lead | _______________ | ____________ | _______ |
| Product Manager | _______________ | ____________ | _______ |

---

**Next checkpoint:** PH1 Gate · 28 Sep 2026 · Foundation Demo
