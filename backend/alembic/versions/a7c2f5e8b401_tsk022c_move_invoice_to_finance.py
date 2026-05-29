"""TSK-022C: drop project_invoices, create invoices in finance domain.

Revision ID: a7c2f5e8b401
Revises: eab2758c6137
Create Date: 2026-05-29 03:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a7c2f5e8b401"
down_revision: str | Sequence[str] | None = "eab2758c6137"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ─── 1. Drop project_invoices (data hilang — dev env, no prod data) ────
    op.drop_index(
        op.f("ix_project_invoices_project_id"), table_name="project_invoices"
    )
    op.drop_table("project_invoices")

    # ─── 2. Create new invoices table in finance domain ────────────────────
    # Catatan: trigger_phase_id FK ke project_phases dengan use_alter=True,
    # akan di-add saat TSK-022B membuat tabel project_phases.
    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invoice_no", sa.String(length=50), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("trigger_phase_id", sa.Uuid(), nullable=True),
        sa.Column("client_id", sa.Uuid(), nullable=True),
        sa.Column("client_name_snapshot", sa.String(length=200), nullable=True),
        sa.Column("termin_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="IDR"),
        sa.Column(
            "tax_pct", sa.Numeric(precision=5, scale=2), nullable=False, server_default="11.0"
        ),
        sa.Column(
            "tax_amount", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"
        ),
        sa.Column("total_amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("notified_finance_at", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column(
            "paid_amount", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"
        ),
        sa.Column("paid_at", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        # trigger_phase_id FK akan di-add di TSK-022B (gunakan add_column + alter_column)
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_no", name="invoices_invoice_no_key"),
    )
    op.create_index(op.f("ix_invoices_invoice_no"), "invoices", ["invoice_no"], unique=False)
    op.create_index(op.f("ix_invoices_project_id"), "invoices", ["project_id"], unique=False)
    op.create_index(op.f("ix_invoices_client_id"), "invoices", ["client_id"], unique=False)
    op.create_index(op.f("ix_invoices_status"), "invoices", ["status"], unique=False)


def downgrade() -> None:
    # ─── 1. Drop invoices ──────────────────────────────────────────────────
    op.drop_index(op.f("ix_invoices_status"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_client_id"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_project_id"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_invoice_no"), table_name="invoices")
    op.drop_table("invoices")

    # ─── 2. Recreate project_invoices ──────────────────────────────────────
    op.create_table(
        "project_invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_no", sa.String(length=50), nullable=False),
        sa.Column("termin_pct", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("trigger_milestone_id", sa.Uuid(), nullable=True),
        sa.Column("trigger_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("notified_finance_at", sa.Date(), nullable=True),
        sa.Column(
            "paid_amount", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"
        ),
        sa.Column("paid_at", sa.Date(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["trigger_milestone_id"], ["project_milestones.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_no", name="project_invoices_invoice_no_key"),
    )
    op.create_index(
        op.f("ix_project_invoices_project_id"), "project_invoices", ["project_id"], unique=False
    )
