"""TSK-107: placement_amendments table for rate/end_date history.

Revision ID: d5a8c1f3e904
Revises: c8f4a3e5d702
Create Date: 2026-05-30 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "d5a8c1f3e904"
down_revision: str | Sequence[str] | None = "c8f4a3e5d702"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "placement_amendments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("placement_id", sa.Uuid(), nullable=False),
        sa.Column("amendment_no", sa.String(length=50), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("old_end_date", sa.Date(), nullable=True),
        sa.Column("old_billing_rate", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("new_end_date", sa.Date(), nullable=True),
        sa.Column("new_billing_rate", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("document_url", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["placement_id"], ["outsource_placements.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("amendment_no", name="placement_amendments_amendment_no_key"),
    )
    op.create_index(
        op.f("ix_placement_amendments_placement_id"),
        "placement_amendments", ["placement_id"], unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_placement_amendments_placement_id"), table_name="placement_amendments",
    )
    op.drop_table("placement_amendments")
