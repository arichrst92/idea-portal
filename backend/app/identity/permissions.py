"""Permission catalog — systematic permission codes untuk RBAC engine.

Konvensi:
- Permission code format: "<resource>.<action>"
- Resources: dept-domain singular (employee, project, payroll, ...)
- Actions: view, create, edit, delete, approve, export, configure

Per CLAUDE.md "12 permission matrix rules per modul per role".

Permission catalog ini di-seed ke DB via app/seed.py.
Role → permissions mapping juga di seed.
"""

from enum import StrEnum


class Resource(StrEnum):
    """Modul/resource yang punya permission set."""

    # System
    USER = "user"
    ROLE = "role"
    AUDIT_LOG = "audit_log"

    # People
    EMPLOYEE = "employee"
    HIRING = "hiring"
    ONBOARDING = "onboarding"
    LAYOFF = "layoff"
    SP = "sp"  # Surat Peringatan internal
    SPO = "spo"  # Surat Peringatan outsource
    OKR = "okr"
    ASSESSMENT = "assessment"
    LEAVE = "leave"
    REIMBURSEMENT = "reimbursement"

    # Work
    PROJECT = "project"
    TIMESHEET = "timesheet"
    BERITA_ACARA = "berita_acara"
    OUTSOURCE = "outsource"
    CLIENT_COMPLAINT = "client_complaint"

    # Sales
    LEAD = "lead"
    PROPOSAL = "proposal"
    SALES_TARGET = "sales_target"

    # Finance
    TRANSACTION = "transaction"
    INVOICE = "invoice"
    PAYROLL = "payroll"
    PROCUREMENT = "procurement"
    FINANCIAL_REPORT = "financial_report"

    # Executive
    EXECUTIVE_DASHBOARD = "executive_dashboard"
    PNL_EBITDA = "pnl_ebitda"
    AI_SUMMARY = "ai_summary"
    PEOPLE_ANALYTICS = "people_analytics"
    PROJECT_HEALTH = "project_health"

    # Content
    BROADCAST = "broadcast"
    EVENT = "event"
    COMPANY_INFO = "company_info"


class Action(StrEnum):
    """Verb action."""

    VIEW = "view"
    CREATE = "create"
    EDIT = "edit"
    DELETE = "delete"
    APPROVE = "approve"
    EXPORT = "export"
    CONFIGURE = "configure"
    OVERRIDE = "override"  # untuk Direktur Utama override decisions


def perm(resource: Resource, action: Action) -> str:
    """Helper: build permission code dari resource + action."""
    return f"{resource.value}.{action.value}"


# ─── Permission registry — semua permission yang dikenal ──────────
# Format: (code, resource, action, description)
# Di-seed ke DB via seed_permissions() di app/seed.py.

PERMISSION_REGISTRY: list[tuple[str, Resource, Action, str]] = [
    # System administration
    (perm(Resource.USER, Action.VIEW), Resource.USER, Action.VIEW, "Lihat data user"),
    (perm(Resource.USER, Action.CREATE), Resource.USER, Action.CREATE, "Buat user baru"),
    (perm(Resource.USER, Action.EDIT), Resource.USER, Action.EDIT, "Edit data user"),
    (perm(Resource.USER, Action.DELETE), Resource.USER, Action.DELETE, "Soft-delete user"),
    (perm(Resource.ROLE, Action.CONFIGURE), Resource.ROLE, Action.CONFIGURE, "Konfigurasi role + permission"),
    (perm(Resource.AUDIT_LOG, Action.VIEW), Resource.AUDIT_LOG, Action.VIEW, "Lihat audit log"),
    (perm(Resource.AUDIT_LOG, Action.EXPORT), Resource.AUDIT_LOG, Action.EXPORT, "Export audit log"),

    # Employee management
    (perm(Resource.EMPLOYEE, Action.VIEW), Resource.EMPLOYEE, Action.VIEW, "Lihat data karyawan (semua dept)"),
    (perm(Resource.EMPLOYEE, Action.CREATE), Resource.EMPLOYEE, Action.CREATE, "Tambah karyawan baru"),
    (perm(Resource.EMPLOYEE, Action.EDIT), Resource.EMPLOYEE, Action.EDIT, "Edit data karyawan"),
    (perm(Resource.EMPLOYEE, Action.EXPORT), Resource.EMPLOYEE, Action.EXPORT, "Export laporan karyawan"),

    # Hiring & lifecycle
    (perm(Resource.HIRING, Action.CREATE), Resource.HIRING, Action.CREATE, "Submit hiring request"),
    (perm(Resource.HIRING, Action.APPROVE), Resource.HIRING, Action.APPROVE, "Approve hiring (Layer 1/2)"),
    (perm(Resource.HIRING, Action.VIEW), Resource.HIRING, Action.VIEW, "Lihat hiring requests"),
    (perm(Resource.ONBOARDING, Action.VIEW), Resource.ONBOARDING, Action.VIEW, "Lihat onboarding checklist"),
    (perm(Resource.ONBOARDING, Action.EDIT), Resource.ONBOARDING, Action.EDIT, "Update onboarding progress"),
    (perm(Resource.LAYOFF, Action.CREATE), Resource.LAYOFF, Action.CREATE, "Submit layoff request"),
    (perm(Resource.LAYOFF, Action.APPROVE), Resource.LAYOFF, Action.APPROVE, "Approve layoff"),

    # SP (Surat Peringatan)
    (perm(Resource.SP, Action.VIEW), Resource.SP, Action.VIEW, "Lihat SP (own atau as approver)"),
    (perm(Resource.SP, Action.CREATE), Resource.SP, Action.CREATE, "Issue SP1/SP2/SP3"),
    (perm(Resource.SP, Action.APPROVE), Resource.SP, Action.APPROVE, "Approve SP draft"),
    (perm(Resource.SPO, Action.CREATE), Resource.SPO, Action.CREATE, "Issue SP-O outsource"),
    (perm(Resource.SPO, Action.APPROVE), Resource.SPO, Action.APPROVE, "Approve SP-O"),

    # OKR & Assessment
    (perm(Resource.OKR, Action.CREATE), Resource.OKR, Action.CREATE, "Set OKR untuk team"),
    (perm(Resource.OKR, Action.EDIT), Resource.OKR, Action.EDIT, "Update OKR progress"),
    (perm(Resource.ASSESSMENT, Action.CREATE), Resource.ASSESSMENT, Action.CREATE, "Submit penilaian bulanan"),
    (perm(Resource.ASSESSMENT, Action.VIEW), Resource.ASSESSMENT, Action.VIEW, "Lihat penilaian (own + team)"),
    (perm(Resource.ASSESSMENT, Action.CONFIGURE), Resource.ASSESSMENT, Action.CONFIGURE, "Konfigurasi bobot scoring (GM/C-Level)"),

    # Leave & reimbursement
    (perm(Resource.LEAVE, Action.CREATE), Resource.LEAVE, Action.CREATE, "Submit cuti"),
    (perm(Resource.LEAVE, Action.APPROVE), Resource.LEAVE, Action.APPROVE, "Approve cuti"),
    (perm(Resource.REIMBURSEMENT, Action.CREATE), Resource.REIMBURSEMENT, Action.CREATE, "Submit reimbursement"),
    (perm(Resource.REIMBURSEMENT, Action.APPROVE), Resource.REIMBURSEMENT, Action.APPROVE, "Approve reimbursement"),

    # Project
    (perm(Resource.PROJECT, Action.CREATE), Resource.PROJECT, Action.CREATE, "Buat project baru"),
    (perm(Resource.PROJECT, Action.EDIT), Resource.PROJECT, Action.EDIT, "Edit project (PM only)"),
    (perm(Resource.PROJECT, Action.VIEW), Resource.PROJECT, Action.VIEW, "Lihat project list"),
    (perm(Resource.PROJECT, Action.OVERRIDE), Resource.PROJECT, Action.OVERRIDE, "Override close project (Direktur only)"),

    # Outsource
    (perm(Resource.OUTSOURCE, Action.VIEW), Resource.OUTSOURCE, Action.VIEW, "Lihat outsource placements"),
    (perm(Resource.OUTSOURCE, Action.EDIT), Resource.OUTSOURCE, Action.EDIT, "Manage placement"),
    (perm(Resource.TIMESHEET, Action.CREATE), Resource.TIMESHEET, Action.CREATE, "Input timesheet"),
    (perm(Resource.TIMESHEET, Action.APPROVE), Resource.TIMESHEET, Action.APPROVE, "Approve timesheet"),
    (perm(Resource.BERITA_ACARA, Action.CREATE), Resource.BERITA_ACARA, Action.CREATE, "Generate BA"),
    (perm(Resource.CLIENT_COMPLAINT, Action.CREATE), Resource.CLIENT_COMPLAINT, Action.CREATE, "Log client complaint"),

    # Sales
    (perm(Resource.LEAD, Action.CREATE), Resource.LEAD, Action.CREATE, "Buat lead baru"),
    (perm(Resource.LEAD, Action.EDIT), Resource.LEAD, Action.EDIT, "Edit lead (own atau as manager)"),
    (perm(Resource.LEAD, Action.VIEW), Resource.LEAD, Action.VIEW, "Lihat sales pipeline"),
    (perm(Resource.PROPOSAL, Action.CREATE), Resource.PROPOSAL, Action.CREATE, "Buat proposal"),
    (perm(Resource.PROPOSAL, Action.APPROVE), Resource.PROPOSAL, Action.APPROVE, "Approve proposal sebelum kirim"),
    (perm(Resource.SALES_TARGET, Action.CONFIGURE), Resource.SALES_TARGET, Action.CONFIGURE, "Set target sales"),

    # Finance
    (perm(Resource.TRANSACTION, Action.CREATE), Resource.TRANSACTION, Action.CREATE, "Input transaksi harian"),
    (perm(Resource.TRANSACTION, Action.APPROVE), Resource.TRANSACTION, Action.APPROVE, "Verify transaksi"),
    (perm(Resource.INVOICE, Action.VIEW), Resource.INVOICE, Action.VIEW, "Lihat invoice"),
    (perm(Resource.INVOICE, Action.CREATE), Resource.INVOICE, Action.CREATE, "Buat invoice"),
    (perm(Resource.PAYROLL, Action.VIEW), Resource.PAYROLL, Action.VIEW, "Lihat payroll (own untuk staff, semua untuk Finance)"),
    (perm(Resource.PAYROLL, Action.CREATE), Resource.PAYROLL, Action.CREATE, "Trigger payroll run"),
    (perm(Resource.PAYROLL, Action.EDIT), Resource.PAYROLL, Action.EDIT, "Input attendance/komponen variable payroll (Operation)"),
    (perm(Resource.PAYROLL, Action.APPROVE), Resource.PAYROLL, Action.APPROVE, "Approve payroll (GM/C-Level Finance)"),
    (perm(Resource.PROCUREMENT, Action.CREATE), Resource.PROCUREMENT, Action.CREATE, "Submit pengadaan"),
    (perm(Resource.PROCUREMENT, Action.APPROVE), Resource.PROCUREMENT, Action.APPROVE, "Approve pengadaan"),
    (perm(Resource.FINANCIAL_REPORT, Action.VIEW), Resource.FINANCIAL_REPORT, Action.VIEW, "Lihat laporan keuangan"),
    (perm(Resource.FINANCIAL_REPORT, Action.EXPORT), Resource.FINANCIAL_REPORT, Action.EXPORT, "Export financial report"),

    # Executive Portal (Direktur Utama + Wakil Direktur Utama)
    (perm(Resource.EXECUTIVE_DASHBOARD, Action.VIEW), Resource.EXECUTIVE_DASHBOARD, Action.VIEW, "Akses Executive Dashboard"),
    (perm(Resource.PNL_EBITDA, Action.VIEW), Resource.PNL_EBITDA, Action.VIEW, "Lihat P&L + EBITDA detail"),
    (perm(Resource.AI_SUMMARY, Action.VIEW), Resource.AI_SUMMARY, Action.VIEW, "Akses AI Executive Summary"),
    (perm(Resource.PEOPLE_ANALYTICS, Action.VIEW), Resource.PEOPLE_ANALYTICS, Action.VIEW, "Lihat People Analytics dashboard"),
    (perm(Resource.PROJECT_HEALTH, Action.VIEW), Resource.PROJECT_HEALTH, Action.VIEW, "Lihat Project Health dashboard"),

    # Content management
    (perm(Resource.BROADCAST, Action.CREATE), Resource.BROADCAST, Action.CREATE, "Buat broadcast (Manager+)"),
    (perm(Resource.EVENT, Action.CREATE), Resource.EVENT, Action.CREATE, "Buat event"),
    (perm(Resource.COMPANY_INFO, Action.EDIT), Resource.COMPANY_INFO, Action.EDIT, "Edit Info Perusahaan CMS"),
]


# ─── Role → Permission mapping ────────────────────────────────────
# Mapping di-seed ke role_permissions table.
# Wakil Direktur Utama = IDENTIK Direktur Utama (knowledge.md sec.2 + US-EX-005).
# Per CLAUDE.md NC-EX-005: audit log harus tetap record persona name eksplisit.

# Permissions yang HANYA Direktur Utama + Wakil Direktur Utama bisa
EXECUTIVE_ONLY_PERMISSIONS: set[str] = {
    perm(Resource.PROJECT, Action.OVERRIDE),
    perm(Resource.EXECUTIVE_DASHBOARD, Action.VIEW),
    perm(Resource.PNL_EBITDA, Action.VIEW),
    perm(Resource.AI_SUMMARY, Action.VIEW),
    perm(Resource.PEOPLE_ANALYTICS, Action.VIEW),
    perm(Resource.PROJECT_HEALTH, Action.VIEW),
    perm(Resource.ROLE, Action.CONFIGURE),
}

# Direktur Utama dapat SEMUA permissions
DIREKTUR_UTAMA_PERMISSIONS: set[str] = {code for code, _, _, _ in PERMISSION_REGISTRY}

# Wakil Direktur Utama dapat SEMUA permissions identik Direktur Utama
WAKIL_DIREKTUR_PERMISSIONS: set[str] = DIREKTUR_UTAMA_PERMISSIONS.copy()

# C-Level — semua kecuali yang executive-only override
C_LEVEL_PERMISSIONS: set[str] = DIREKTUR_UTAMA_PERMISSIONS - EXECUTIVE_ONLY_PERMISSIONS

# GM — dept head: kebanyakan approve permission + view
GM_PERMISSIONS: set[str] = {
    perm(Resource.EMPLOYEE, Action.VIEW),
    perm(Resource.EMPLOYEE, Action.EDIT),
    perm(Resource.EMPLOYEE, Action.EXPORT),
    perm(Resource.HIRING, Action.APPROVE),
    perm(Resource.HIRING, Action.VIEW),
    perm(Resource.LAYOFF, Action.APPROVE),
    perm(Resource.ONBOARDING, Action.VIEW),
    perm(Resource.ONBOARDING, Action.EDIT),
    perm(Resource.SP, Action.VIEW),
    perm(Resource.SP, Action.APPROVE),
    perm(Resource.SPO, Action.APPROVE),
    perm(Resource.OKR, Action.CREATE),
    perm(Resource.OKR, Action.EDIT),
    perm(Resource.ASSESSMENT, Action.CREATE),
    perm(Resource.ASSESSMENT, Action.VIEW),
    perm(Resource.ASSESSMENT, Action.CONFIGURE),
    perm(Resource.LEAVE, Action.CREATE),
    perm(Resource.LEAVE, Action.APPROVE),
    perm(Resource.REIMBURSEMENT, Action.CREATE),
    perm(Resource.REIMBURSEMENT, Action.APPROVE),
    perm(Resource.PROJECT, Action.CREATE),
    perm(Resource.PROJECT, Action.EDIT),
    perm(Resource.PROJECT, Action.VIEW),
    perm(Resource.OUTSOURCE, Action.VIEW),
    perm(Resource.OUTSOURCE, Action.EDIT),
    perm(Resource.TIMESHEET, Action.APPROVE),
    perm(Resource.CLIENT_COMPLAINT, Action.CREATE),
    perm(Resource.LEAD, Action.VIEW),
    perm(Resource.PROPOSAL, Action.APPROVE),
    perm(Resource.SALES_TARGET, Action.CONFIGURE),
    perm(Resource.TRANSACTION, Action.APPROVE),
    perm(Resource.INVOICE, Action.VIEW),
    perm(Resource.INVOICE, Action.CREATE),
    perm(Resource.PAYROLL, Action.VIEW),
    perm(Resource.PAYROLL, Action.APPROVE),
    perm(Resource.PROCUREMENT, Action.APPROVE),
    perm(Resource.FINANCIAL_REPORT, Action.VIEW),
    perm(Resource.FINANCIAL_REPORT, Action.EXPORT),
    perm(Resource.BROADCAST, Action.CREATE),
    perm(Resource.EVENT, Action.CREATE),
    perm(Resource.AUDIT_LOG, Action.VIEW),
}

# Manager — middle management, approve Layer 1
MANAGER_PERMISSIONS: set[str] = {
    perm(Resource.EMPLOYEE, Action.VIEW),
    perm(Resource.HIRING, Action.CREATE),
    perm(Resource.HIRING, Action.APPROVE),
    perm(Resource.HIRING, Action.VIEW),
    perm(Resource.LAYOFF, Action.CREATE),
    perm(Resource.ONBOARDING, Action.VIEW),
    perm(Resource.SP, Action.VIEW),
    perm(Resource.OKR, Action.CREATE),
    perm(Resource.OKR, Action.EDIT),
    perm(Resource.ASSESSMENT, Action.CREATE),
    perm(Resource.ASSESSMENT, Action.VIEW),
    perm(Resource.LEAVE, Action.CREATE),
    perm(Resource.LEAVE, Action.APPROVE),
    perm(Resource.REIMBURSEMENT, Action.CREATE),
    perm(Resource.REIMBURSEMENT, Action.APPROVE),
    perm(Resource.PROJECT, Action.CREATE),
    perm(Resource.PROJECT, Action.EDIT),
    perm(Resource.PROJECT, Action.VIEW),
    perm(Resource.OUTSOURCE, Action.VIEW),
    perm(Resource.TIMESHEET, Action.APPROVE),
    perm(Resource.LEAD, Action.CREATE),
    perm(Resource.LEAD, Action.EDIT),
    perm(Resource.LEAD, Action.VIEW),
    perm(Resource.PROPOSAL, Action.CREATE),
    perm(Resource.INVOICE, Action.VIEW),
    perm(Resource.PAYROLL, Action.VIEW),
    perm(Resource.PROCUREMENT, Action.CREATE),
    perm(Resource.BROADCAST, Action.CREATE),
    perm(Resource.EVENT, Action.CREATE),
}

# Lead — team lead, limited approval
LEAD_PERMISSIONS: set[str] = {
    perm(Resource.EMPLOYEE, Action.VIEW),
    perm(Resource.OKR, Action.EDIT),
    perm(Resource.ASSESSMENT, Action.CREATE),
    perm(Resource.ASSESSMENT, Action.VIEW),
    perm(Resource.LEAVE, Action.CREATE),
    perm(Resource.LEAVE, Action.APPROVE),  # Layer 1 untuk staff
    perm(Resource.REIMBURSEMENT, Action.CREATE),
    perm(Resource.PROJECT, Action.EDIT),
    perm(Resource.PROJECT, Action.VIEW),
    perm(Resource.TIMESHEET, Action.CREATE),
    perm(Resource.LEAD, Action.CREATE),
    perm(Resource.LEAD, Action.EDIT),
    perm(Resource.LEAD, Action.VIEW),
    perm(Resource.PROPOSAL, Action.CREATE),
    perm(Resource.PAYROLL, Action.VIEW),
    perm(Resource.PROCUREMENT, Action.CREATE),
}

# Staff — basic self-service
STAFF_PERMISSIONS: set[str] = {
    perm(Resource.EMPLOYEE, Action.VIEW),  # own profile only — enforce di service layer
    perm(Resource.ASSESSMENT, Action.VIEW),  # own only
    perm(Resource.LEAVE, Action.CREATE),
    perm(Resource.REIMBURSEMENT, Action.CREATE),
    perm(Resource.PROJECT, Action.VIEW),  # member-only
    perm(Resource.TIMESHEET, Action.CREATE),  # untuk outsource
    perm(Resource.PAYROLL, Action.VIEW),  # own slip
    perm(Resource.PROCUREMENT, Action.CREATE),
}


ROLE_PERMISSION_MAP: dict[str, set[str]] = {
    "DIREKTUR_UTAMA": DIREKTUR_UTAMA_PERMISSIONS,
    "WAKIL_DIREKTUR_UTAMA": WAKIL_DIREKTUR_PERMISSIONS,
    "C_LEVEL": C_LEVEL_PERMISSIONS,
    "GM": GM_PERMISSIONS,
    "MANAGER": MANAGER_PERMISSIONS,
    "LEAD": LEAD_PERMISSIONS,
    "STAFF": STAFF_PERMISSIONS,
}
