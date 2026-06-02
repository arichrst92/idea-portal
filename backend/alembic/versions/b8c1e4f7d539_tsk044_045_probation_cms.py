"""TSK-044 + TSK-045: probation_assessments + cms_articles tables.

Revision ID: b8c1e4f7d539
Revises: a4d7e9f1c628
Create Date: 2026-06-01 11:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "b8c1e4f7d539"
down_revision: str | Sequence[str] | None = "a4d7e9f1c628"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # TSK-044
    op.create_table(
        "probation_assessments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("probation_start", sa.Date(), nullable=False),
        sa.Column("probation_end", sa.Date(), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False, server_default="PENDING"),
        sa.Column("score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("extended_to", sa.Date(), nullable=True),
        sa.Column("reviewer_user_id", sa.Uuid(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"]),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_probation_assessments_employee_id", "probation_assessments", ["employee_id"])
    op.create_index("ix_probation_assessments_decision", "probation_assessments", ["decision"])
    op.create_index("ix_probation_employee_decision", "probation_assessments", ["employee_id", "decision"])

    # TSK-045
    op.create_table(
        "cms_articles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_cms_articles_slug", "cms_articles", ["slug"])
    op.create_index("ix_cms_articles_category", "cms_articles", ["category"])
    op.create_index("ix_cms_articles_is_published", "cms_articles", ["is_published"])
    op.create_index("ix_cms_articles_category_published", "cms_articles", ["category", "is_published"])


def downgrade() -> None:
    op.drop_index("ix_cms_articles_category_published", table_name="cms_articles")
    op.drop_index("ix_cms_articles_is_published", table_name="cms_articles")
    op.drop_index("ix_cms_articles_category", table_name="cms_articles")
    op.drop_index("ix_cms_articles_slug", table_name="cms_articles")
    op.drop_table("cms_articles")
    op.drop_index("ix_probation_employee_decision", table_name="probation_assessments")
    op.drop_index("ix_probation_assessments_decision", table_name="probation_assessments")
    op.drop_index("ix_probation_assessments_employee_id", table_name="probation_assessments")
    op.drop_table("probation_assessments")
