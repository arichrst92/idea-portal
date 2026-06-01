"""TSK-053 + TSK-054: thr_payments table + payroll_slips final flag.

Revision ID: d6f9c2e8b94a
Revises: c1e8a4b2f839
Create Date: 2026-05-31 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "d6f9c2e8b94a"
down_revision: str | Sequence[str] | None = "c1e8a4b2f839"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # TSK-053 — THR Payment table
    op.create_table(
        "thr_payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("thr_year", sa.Integer(), nullable=False),
        sa.Column("base_salary", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("months_worked", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column("thr_amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="IDR"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="GENERATED"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payment_date", sa.Date(), nullable=True),
        sa.Column("transfer_ref", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("generated_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["generated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "thr_year", name="uq_thr_employee_year"),
    )
    op.create_index("ix_thr_payments_employee_id", "thr_payments", ["employee_id"])
    op.create_index("ix_thr_payments_thr_year", "thr_payments", ["thr_year"])
    op.create_index("ix_thr_payments_status", "thr_payments", ["status"])
    op.create_index("ix_thr_year_status", "thr_payments", ["thr_year", "status"])

    # TSK-054 — final payroll flag pada payroll_slips
    with op.batch_alter_table("payroll_slips") as batch:
        batch.add_column(
            sa.Column(
                "is_final_payroll",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(sa.Column("last_working_day", sa.Date(), nullable=True))
        batch.create_index(
            "ix_payroll_slips_is_final_payroll",
            ["is_final_payroll"],
        )


def downgrade() -> None:
    with op.batch_alter_table("payroll_slips") as batch:
        batch.drop_index("ix_payroll_slips_is_final_payroll")
        batch.drop_column("last_working_day")
        batch.drop_column("is_final_payroll")
    op.drop_index("ix_thr_year_status", table_name="thr_payments")
    op.drop_index("ix_thr_payments_status", table_name="thr_payments")
    op.drop_index("ix_thr_payments_thr_year", table_name="thr_payments")
    op.drop_index("ix_thr_payments_employee_id", table_name="thr_payments")
    op.drop_table("thr_payments")
