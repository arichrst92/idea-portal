"""Alembic env — sync engine, async-aware via run_migrations_online.

Import semua domain models di sini agar Alembic autogenerate mendeteksi
schema changes dari Base.metadata.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.database import Base

# ─── Import semua models untuk autogenerate ──────────────────────
# Per ERD knowledge.md sec.20 — 47 tabel di 7 domain
from app.identity.models import (  # noqa: F401  — Identity & Auth (4)
    AuditLog,
    Permission,
    Role,
    RolePermission,
    User,
    UserRole,
)
from app.organization.models import (  # noqa: F401  — Organization (5)
    Department,
    Employee,
    EmployeeContract,
    OrgChange,
    Position,
)
from app.assessment.models import (  # noqa: F401  — Assessment & Performance (7)
    Assessment,
    AssessmentConfig,
    AssessmentItem,
    AssessmentPeriod,
    OkrKeyResult,
    OkrObjective,
    WarningLetter,
)
from app.project.models import (  # noqa: F401  — Project & Work (9 post TSK-070)
    Project,
    ProjectChangeRequest,
    ProjectDocument,
    ProjectEpic,
    ProjectMember,
    ProjectPhase,
    ProjectSubtask,
    ProjectSubtaskComment,
    ProjectTask,
    ProjectTaskComment,
)
from app.finance.models import Invoice  # noqa: F401  — Finance (TSK-022C)
from app.outsource.models import (  # noqa: F401  — Outsource (8)
    BeritaAcara,
    Client,
    ClientComplaint,
    OutsourcePlacement,
    PlacementAmendment,
    Timesheet,
    TimesheetItem,
    WarningLetterOutsource,
)
from app.payroll.models import (  # noqa: F401  — HR & Payroll (12 incl LeaveBalance)
    Holiday,
    LeaveBalance,
    LeaveRequest,
    LeaveType,
    PayrollComponent,
    PayrollConfig,
    PayrollPeriod,
    PayrollSlip,
    ProcurementRequest,
    Reimbursement,
    Vendor,
    WorkCalendar,
)
from app.sales.models import (  # noqa: F401  — Sales (7)
    Lead,
    LeadActivity,
    Proposal,
    ProposalItem,
    SalesActionItem,
    SalesCommission,
    SalesTarget,
)
from app.hiring.models import (  # noqa: F401  — Hiring (3) TSK-015
    Interview,
    JobApplication,
    JobOpening,
)
from app.onboarding.models import (  # noqa: F401  — Onboarding (4) TSK-016
    OnboardingAssignment,
    OnboardingTask,
    OnboardingTemplate,
    TaskCompletion,
)
from app.separation.models import (  # noqa: F401  — Separation (1) TSK-017
    EmployeeSeparation,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override sqlalchemy.url dengan settings runtime
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url_sync)


def run_migrations_offline() -> None:
    """Run migrations in offline mode (generate SQL only)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode (apply to DB)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
