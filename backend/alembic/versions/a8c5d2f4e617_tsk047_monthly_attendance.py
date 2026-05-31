"""TSK-047: monthly_attendances table — Operation input attendance per period.

Revision ID: a8c5d2f4e617
Revises: f4a7c9b1d316
Create Date: 2026-05-31 15:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "a8c5d2f4e617"
down_revision: str | Sequence[str] | None = "f4a7c9b1d316"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "monthly_attendances",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("period_id", sa.Uuid(), nullable=False),
        sa.Column("days_present", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("days_absent_paid", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("days_absent_unpaid", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overtime_hours", sa.Numeric(precision=6, scale=2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("input_by_user_id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(["period_id"], ["payroll_periods.id"]),
        sa.ForeignKeyConstraint(["input_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employee_id", "period_id", name="uq_attendance_employee_period"),
    )
    op.create_index(
        "ix_monthly_attendances_employee_id",
        "monthly_attendances",
        ["employee_id"],
        unique=False,
    )
    op.create_index(
        "ix_monthly_attendances_period_id",
        "monthly_attendances",
        ["period_id"],
        unique=False,
    )
    op.create_index(
        "ix_attendance_period_employee",
        "monthly_attendances",
        ["period_id", "employee_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_attendance_period_employee", table_name="monthly_attendances")
    op.drop_index("ix_monthly_attendances_period_id", table_name="monthly_attendances")
    op.drop_index("ix_monthly_attendances_employee_id", table_name="monthly_attendances")
    op.drop_table("monthly_attendances")
