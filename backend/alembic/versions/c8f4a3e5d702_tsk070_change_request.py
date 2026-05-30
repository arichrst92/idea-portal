"""TSK-070: project_change_requests table.

Revision ID: c8f4a3e5d702
Revises: b3e9d2c1f502
Create Date: 2026-05-30 11:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "c8f4a3e5d702"
down_revision: str | Sequence[str] | None = "b3e9d2c1f502"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_change_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("cr_number", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("impact_category", sa.String(length=20), nullable=False, server_default="MIXED"),
        sa.Column("scope_delta", sa.Text(), nullable=True),
        sa.Column("timeline_delta_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_delta", sa.Numeric(precision=15, scale=2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="IDR"),
        sa.Column("requester_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="DRAFT"),
        sa.Column("layer1_approver_id", sa.Uuid(), nullable=True),
        sa.Column("layer1_approved_at", sa.Date(), nullable=True),
        sa.Column("layer1_notes", sa.Text(), nullable=True),
        sa.Column("layer2_approver_id", sa.Uuid(), nullable=True),
        sa.Column("layer2_approved_at", sa.Date(), nullable=True),
        sa.Column("layer2_notes", sa.Text(), nullable=True),
        sa.Column("rejected_at", sa.Date(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("sales_notified_at", sa.Date(), nullable=True),
        sa.Column("finance_notified_at", sa.Date(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["requester_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["layer1_approver_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["layer2_approver_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cr_number", name="project_change_requests_cr_number_key"),
    )
    op.create_index(
        op.f("ix_project_change_requests_project_id"),
        "project_change_requests", ["project_id"], unique=False,
    )
    op.create_index(
        op.f("ix_project_change_requests_status"),
        "project_change_requests", ["status"], unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_project_change_requests_status"), table_name="project_change_requests",
    )
    op.drop_index(
        op.f("ix_project_change_requests_project_id"), table_name="project_change_requests",
    )
    op.drop_table("project_change_requests")
