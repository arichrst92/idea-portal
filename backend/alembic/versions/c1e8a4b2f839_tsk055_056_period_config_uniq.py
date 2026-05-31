"""TSK-055 + TSK-056: PayrollPeriod cutoff_date + publish_date + unique (year, month).

Revision ID: c1e8a4b2f839
Revises: b9d6e3f5a728
Create Date: 2026-05-31 17:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "c1e8a4b2f839"
down_revision: str | Sequence[str] | None = "b9d6e3f5a728"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # TSK-055 — config columns
    with op.batch_alter_table("payroll_periods") as batch:
        batch.add_column(sa.Column("cutoff_date", sa.Date(), nullable=True))
        batch.add_column(sa.Column("publish_date", sa.Date(), nullable=True))

    # TSK-056 — race-safe unique on (year, month)
    op.create_unique_constraint(
        "uq_payroll_period_year_month",
        "payroll_periods",
        ["year", "month"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_payroll_period_year_month", "payroll_periods", type_="unique"
    )
    with op.batch_alter_table("payroll_periods") as batch:
        batch.drop_column("publish_date")
        batch.drop_column("cutoff_date")
