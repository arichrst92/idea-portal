"""TSK-050: payroll_periods approval audit columns.

Revision ID: b9d6e3f5a728
Revises: a8c5d2f4e617
Create Date: 2026-05-31 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "b9d6e3f5a728"
down_revision: str | Sequence[str] | None = "a8c5d2f4e617"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("payroll_periods") as batch:
        batch.add_column(
            sa.Column("submitted_for_review_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("submitted_by_user_id", sa.Uuid(), nullable=True))
        batch.add_column(
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("approved_by_user_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("approval_notes", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("rejected_by_user_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("rejection_reason", sa.Text(), nullable=True))
        batch.create_foreign_key(
            "fk_payroll_periods_submitted_by_user_id",
            "users",
            ["submitted_by_user_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_payroll_periods_approved_by_user_id",
            "users",
            ["approved_by_user_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_payroll_periods_rejected_by_user_id",
            "users",
            ["rejected_by_user_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("payroll_periods") as batch:
        batch.drop_constraint("fk_payroll_periods_rejected_by_user_id", type_="foreignkey")
        batch.drop_constraint("fk_payroll_periods_approved_by_user_id", type_="foreignkey")
        batch.drop_constraint("fk_payroll_periods_submitted_by_user_id", type_="foreignkey")
        batch.drop_column("rejection_reason")
        batch.drop_column("rejected_by_user_id")
        batch.drop_column("rejected_at")
        batch.drop_column("approval_notes")
        batch.drop_column("approved_by_user_id")
        batch.drop_column("approved_at")
        batch.drop_column("submitted_by_user_id")
        batch.drop_column("submitted_for_review_at")
