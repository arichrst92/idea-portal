"""TSK-108: client_kpi_assessments table.

Revision ID: e9b6f2d4a015
Revises: d5a8c1f3e904
Create Date: 2026-05-30 15:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "e9b6f2d4a015"
down_revision: str | Sequence[str] | None = "d5a8c1f3e904"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "client_kpi_assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("placement_id", sa.Uuid(), nullable=False),
        sa.Column("assessment_period", sa.String(length=20), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("token_expires_at", sa.Date(), nullable=False),
        sa.Column("score_quality", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("score_communication", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("score_attendance", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("score_professionalism", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("score_initiative", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("overall_score", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.Date(), nullable=False),
        sa.Column("submitted_at", sa.Date(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["placement_id"], ["outsource_placements.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="client_kpi_assessments_token_key"),
    )
    op.create_index(
        op.f("ix_client_kpi_assessments_placement_id"),
        "client_kpi_assessments", ["placement_id"], unique=False,
    )
    op.create_index(
        op.f("ix_client_kpi_assessments_token"),
        "client_kpi_assessments", ["token"], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_client_kpi_assessments_token"), table_name="client_kpi_assessments")
    op.drop_index(op.f("ix_client_kpi_assessments_placement_id"), table_name="client_kpi_assessments")
    op.drop_table("client_kpi_assessments")
