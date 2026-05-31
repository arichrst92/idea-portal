# ERD Variable Reference — IDEA Portal

**Last audit:** 2026-05-31 (auto-generated from `backend/app/**/models.py`)
**Purpose:** Single source of truth untuk attribute access pada SQLAlchemy models. Hindari `AttributeError` di runtime.

---

## 🚨 Critical FK Direction Patterns (READ FIRST)

Beberapa FK direction di IDEA Portal counter-intuitive — hafal ini sebelum coding.

### 1. Employee ↔ User

- **FK direction:** `employees.user_id → users.id` (Employee owns the FK)
- `User` has **NO** `employee_id` column. Only `user.employee` relationship (back-populates).
- `Employee` has **NO** `nik` column. NIK lives di `User.nik` (digunakan sebagai login identifier per `knowledge.md` sec.1).

**Get NIK for an Employee:**
```python
# ❌ WRONG — AttributeError 'Employee' has no 'nik'
emp = await session.get(Employee, employee_id)
nik = emp.nik

# ✅ RIGHT — JOIN via FK
stmt = (
    select(User.nik, Employee.full_name)
    .join(User, Employee.user_id == User.id)
    .where(Employee.id == employee_id)
)

# ✅ ALTERNATIVE — explicit lookup
nik = (await session.execute(
    select(User.nik).where(User.id == emp.user_id)
)).scalar_one_or_none()
```

**Get Employee for a User:**
```python
# ❌ WRONG — User has no employee_id
user_obj = await session.get(User, user_id)
emp_id = user_obj.employee_id

# ✅ RIGHT — query Employee.user_id reverse
emp_id = (await session.execute(
    select(Employee.id).where(Employee.user_id == user_id)
)).scalar_one_or_none()

# ✅ ALTERNATIVE — eager-loaded relationship
# (only if relationship is configured to load: lazy='joined' or selectinload)
emp = user_obj.employee  # may be None
```

### 2. Common gotchas

| Wrong | Right | Why |
|---|---|---|
| `Employee.nik` | `User.nik` (JOIN via `user_id`) | NIK is auth credential |
| `User.employee_id` | `Employee.user_id` reverse query | FK ownership |
| `User.department_id` | `Employee.department_id` | User is auth-only |
| `User.full_name` | `Employee.full_name` | User has no name |
| `Department.head_id` | `Department.head_user_id` | Refers to User, not Employee |
| `Project.milestone_id` (in task) | `Project.epic_id` (renamed TSK-022B) | Hierarchy refactored |
| `ProjectInvoice` model | `app.finance.models.Invoice` | Moved TSK-022C |

---

## Full Model Field Map

Format: `ClassName (table_name) — fields...`

### Identity & Auth
- **User** (`users`): `nik, password_hash, email, is_active, is_locked, failed_login_attempts, locked_until, last_login_at, last_login_ip` + `roles`, `employee` (relationships)
- **Role** (`roles`): `code, name, level, description, is_executive` + `permissions, users`
- **Permission** (`permissions`): `code, resource, action, description` + `roles`
- **RolePermission** (`role_permissions`): `role_id, permission_id`
- **UserRole** (`user_roles`): `user_id, role_id, assigned_by_user_id, valid_until` + `user, role`
- **AuditLog** (`audit_logs`): `timestamp, actor_user_id, actor_nik, actor_persona, action, resource_type, resource_id, ip_address, user_agent, before_state, after_state, notes`

### Organization
- **Department** (`departments`): `code, name, head_user_id, description` + `employees, positions`
- **Position** (`positions`): `code, name, department_id, level, salary_range_min, salary_range_max` + `department`
- **Employee** (`employees`): `user_id, full_name, photo_url, date_of_birth, gender, phone_number, address, emergency_contact, employee_type, status, department_id, position_id, supervisor_id, joined_date, probation_end_date, last_working_day, bank_name, bank_account, npwp` + `user, department, position`
- **EmployeeContract** (`employee_contracts`): `employee_id, contract_type, start_date, end_date, salary, document_url, is_active`
- **OrgChange** (`org_changes`): `employee_id, change_type, effective_date, before_snapshot, after_snapshot, reason, approved_by_user_id, initiated_by_user_id`

### Hiring (M1.3)
- **JobOpening** (`job_openings`): `title, description, requirements, department_id, position_id, status, slots_needed, slots_filled, min_salary, max_salary, currency, posted_date, deadline, closed_date, requested_by_user_id, approved_by_user_id, approved_at, rejection_reason, is_public` + `applications`
- **JobApplication** (`job_applications`): `job_opening_id, candidate_name, candidate_email, candidate_phone, resume_url, cover_letter, linkedin_url, source, referrer_user_id, stage, stage_changed_at, rejection_reason, rejection_stage, notes, offered_salary, offered_start_date` + `job_opening, interviews`
- **Interview** (`interviews`): `application_id, interview_type, scheduled_at, duration_minutes, location_or_link, interviewer_user_ids, result, feedback, score` + `application`

### Onboarding (M1.3)
- **OnboardingTemplate** (`onboarding_templates`): `name, description, target_department_id, target_position_level, estimated_duration_days, is_active` + `tasks, assignments`
- **OnboardingTask** (`onboarding_tasks`): `template_id, category, title, description, instructions, order_index, default_due_offset_days, assigned_role, is_required, reference_url` + `template`
- **OnboardingAssignment** (`onboarding_assignments`): `employee_id, template_id, status, started_at, target_completion_date, completed_at, assigned_by_user_id, notes` + `template, completions`
- **TaskCompletion** (`task_completions`): `assignment_id, task_id, status, due_date, completed_at, completed_by_user_id, notes, blocker_reason` + `assignment, task`

### Separation (M1.3)
- **EmployeeSeparation** (`employee_separations`): `employee_id, separation_type, status, reason, effective_date, notice_period_days, severance_amount, currency, assets_to_return, related_warning_letter_id, exit_interview_notes, exit_interview_completed_at, initiated_by_user_id, approval_l1_user_id, approval_l1_at, approval_l1_notes, approval_l2_user_id, approval_l2_at, approval_l2_notes, rejected_by_user_id, rejected_at, rejection_reason, executed_by_user_id, executed_at, cancelled_at, cancellation_reason`

### Assessment & Performance (M2.1)
- **AssessmentConfig** (`assessment_configs`): `department_id, okr_weight_pct, weighted_weight_pct, effective_date, configured_by_user_id`
- **AssessmentItem** (`assessment_items`): `config_id, code, name, weight_pct`
- **AssessmentPeriod** (`assessment_periods`): `year, month, is_closed`
- **Assessment** (`assessments`): `employee_id, period_id, okr_score, weighted_score, final_score, notes, submitted_by_user_id`
- **OkrObjective** (`okr_objectives`): `employee_id, year, quarter, objective, set_by_user_id`
- **OkrKeyResult** (`okr_key_results`): `objective_id, description, target, achieved, progress_pct`
- **WarningLetter** (`warning_letters`): `employee_id, level, issued_date, reason, document_url, is_ai_drafted, acknowledged_at, approved_by_user_id`

### Project Management (M2.1, refactored TSK-022B+C)
- **Project** (`projects`): `code, name, type, status, description, pm_user_id, client_id, start_date, end_date, contract_value, currency, task_slug_counter`
- **ProjectMember** (`project_members`): `project_id, employee_id, role, allocation_pct, start_date, end_date`
- **ProjectPhase** (`project_phases`): `project_id, name, description, order_index, target_date, completed_at, status, progress_pct` — replaces deprecated `project_milestones`
- **ProjectEpic** (`project_epics`): `phase_id, project_id, name, description, order_index, status, color`
- **ProjectTask** (`project_tasks`): `project_id, epic_id, slug, title, description, assignee_id, status, priority, story_points, due_date`
- **ProjectSubtask** (`project_subtasks`): `task_id, slug, title, description, assignee_id, status, story_points, due_date, order_index`
- **ProjectTaskComment** (`project_task_comments`): `task_id, author_user_id, body`
- **ProjectSubtaskComment** (`project_subtask_comments`): `subtask_id, author_user_id, body`
- **ProjectDocument** (`project_documents`): `project_id, name, folder_path, file_url, version, uploaded_by_user_id`
- **ProjectChangeRequest** (`project_change_requests`): `project_id, cr_number, title, description, impact_category, scope_delta, timeline_delta_days, cost_delta, currency, requester_user_id, status, layer1_*, layer2_*, rejected_*, sales_notified_at, finance_notified_at`

### Finance (TSK-022C, M2.2)
- **Invoice** (`invoices`): `invoice_no, project_id, trigger_phase_id, client_id, client_name_snapshot, termin_pct, amount, currency, tax_pct, tax_amount, total_amount, issue_date, due_date, notified_finance_at, status, paid_amount, paid_at, notes` — moved from `app.project.models.ProjectInvoice`

### Sales (M3.1)
- **Lead** (`leads`): `company_name, pic_name, pic_email, pic_phone, services, stage, estimated_value, currency, source, assigned_to_user_id, referred_by_user_id, is_direktur_driven, closed_at`
- **LeadActivity** (`lead_activities`): `lead_id, activity_date, activity_type, notes, logged_by_user_id`
- **Proposal** (`proposals`): `lead_id, proposal_no, version, total_value, pdf_url, status, approved_by_user_id, sent_at`
- **ProposalItem** (`proposal_items`): `proposal_id, description, quantity, unit_price, subtotal`
- **SalesTarget** (`sales_targets`): `user_id, department_id, year, month, target_amount, currency`
- **SalesActionItem** (`sales_action_items`): `lead_id, suggestion, is_ai_generated, status, suggested_due_date`
- **SalesCommission** (`sales_commissions`): `lead_id, sales_user_id, commission_pct, commission_amount, target_payroll_period_id, status`

### Outsource (M2.3)
- **Client** (`clients`): `code, name, pic_name, pic_email, pic_phone, address, is_active`
- **OutsourcePlacement** (`outsource_placements`): `employee_id, client_id, role_at_client, start_date, end_date, billing_type, billing_rate, is_active`
- **PlacementAmendment** (`placement_amendments`): `placement_id, amendment_no, effective_date, old_end_date, old_billing_rate, new_end_date, new_billing_rate, document_url, notes, created_by_user_id`
- **Timesheet** (`timesheets`): `placement_id, year, month, workdays_count, status, submitted_at, approved_at`
- **TimesheetItem** (`timesheet_items`): `timesheet_id, work_date, is_present, notes`
- **BeritaAcara** (`berita_acara`): `timesheet_id, ba_no, pdf_url, signed_by_ide, signed_by_client, client_signature_token, client_signed_at`
- **ClientComplaint** (`client_complaints`): `placement_id, complaint_date, severity, description, logged_by_user_id, resolved_at`
- **ClientKpiAssessment** (`client_kpi_assessments`): `placement_id, assessment_period, token, token_expires_at, score_quality, score_communication, score_attendance, score_professionalism, score_initiative, overall_score, feedback, sent_at, submitted_at, created_by_user_id`
- **WarningLetterOutsource** (`warning_letters_outsource`): `placement_id, level, issued_date, triggered_by_complaint_id, reason, evaluation_end_date, triggers_replacement`

### Payroll (M1.4, M2.2)
- **PayrollConfig** (`payroll_configs`): `employee_id, basic_salary, fixed_allowance, bpjs_kesehatan_pct, bpjs_ketenagakerjaan_pct, effective_date`
- **PayrollPeriod** (`payroll_periods`): `year, month, pay_date, status, locked_at`
- **PayrollComponent** (`payroll_components`): `slip_id, code, name, component_type, is_variable, amount, source_reference`
- **PayrollSlip** (`payroll_slips`): `employee_id, period_id, slip_no, gross_income, total_deductions, take_home_pay, pdf_url, published_at`
- **LeaveType** (`leave_types`): `code, name, default_days_per_year, is_paid`
- **LeaveRequest** (`leave_requests`): `employee_id, leave_type_id, start_date, end_date, days_count, reason, status, layer1_*, layer2_*, rejected_*, cancelled_at`
- **LeaveBalance** (`leave_balances`): `employee_id, leave_type_id, year, allocated_days, used_days, carried_over_days`
- **Reimbursement** (`reimbursements`): `employee_id, request_date, category, amount, currency, description, receipt_url, project_id, status, layer1_*, layer2_*, rejected_*, cancelled_at, transferred_at, transferred_by_user_id, transfer_reference`
- **Vendor** (`vendors`): `code, name, contact_info`
- **ProcurementRequest** (`procurement_requests`): `requested_by_user_id, request_date, item_description, item_category, quantity, estimated_amount, actual_amount, currency, vendor_id, is_asset, expected_delivery_date, actual_delivery_date, notes, status, layer1_*, layer2_*, rejected_*, cancelled_at, po_number, ordered_at`
- **WorkCalendar** (`work_calendars`): `year, department_id, workdays_per_week, workhours_per_day`
- **Holiday** (`holidays`): `holiday_date, name, is_joint_leave`

---

## Audit Workflow (Re-run Anytime)

Saat menambah model atau bingung field availability, jalankan:

```bash
# Generate model map
python3 ~/Library/Application\ Support/Claude/local-agent-mode-sessions/efa1017c-8be2-495d-b3c3-6169e290a5f3/ea2461f8-f490-415c-959f-b260e752296d/local_2a0a76e2-8e02-430b-8195-d9b9fe1c95ff/outputs/audit_models.py
# → outputs/model_map.txt (canonical field list)

# Detect Model.attr SQL access violations
python3 .../outputs/audit_usage.py
# → outputs/erd_audit.txt

# Detect instance access bugs (Employee.nik etc.)
python3 .../outputs/audit_instances.py
# → outputs/instance_audit.txt
```

Audit script lives di `outputs/` folder (Cowork scratchpad). Run after any model migration or saat ada error AttributeError mencurigakan.

---

## Lesson Learned (Past Bugs Fixed)

| Date | Bug | Fix Pattern |
|---|---|---|
| 2026-05-31 | Multiple endpoints `Employee.nik` crash 500 | JOIN User via `Employee.user_id == User.id`, select `User.nik` |
| 2026-05-31 | `User.employee_id` crash in sales/payroll/project router | Query Employee.user_id reverse: `select(Employee.id).where(Employee.user_id == user_id)` |
| 2026-05-31 | `/projects/my-tasks-due-summary` 422 — route collision | FastAPI route order matters: `/projects/{id}` matches first. Static routes harus didaftar SEBELUM dynamic, atau pakai namespace `/me/*`. |
