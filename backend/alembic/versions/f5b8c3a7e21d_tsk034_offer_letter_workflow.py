"""TSK-034: offering letter workflow on job_applications.

Revision ID: f5b8c3a7e21d
Revises: e3a7b9d2c54f
Create Date: 2026-06-01 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "f5b8c3a7e21d"
down_revision: str | Sequence[str] | None = "e3a7b9d2c54f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("job_applications") as batch:
        batch.add_column(
            sa.Column(
                "offer_status",
                sa.String(length=20),
                nullable=False,
                server_default="DRAFT",
            )
        )
        batch.add_column(sa.Column("offer_pdf_url", sa.String(length=500), nullable=True))
        batch.add_column(
            sa.Column("offer_pdf_generated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("offer_additional_terms", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column(
                "salary_override_approved",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(
            sa.Column("offer_submitted_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("offer_submitted_by_user_id", sa.Uuid(), nullable=True))
        batch.add_column(
            sa.Column("offer_approved_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("offer_approved_by_user_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("offer_approval_notes", sa.Text(), nullable=True))
        batch.add_column(
            sa.Column("offer_sent_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("candidate_response", sa.String(length=20), nullable=True))
        batch.add_column(
            sa.Column("candidate_response_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("candidate_response_notes", sa.Text(), nullable=True))

        batch.create_foreign_key(
            "fk_job_applications_offer_submitted_by",
            "users",
            ["offer_submitted_by_user_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_job_applications_offer_approved_by",
            "users",
            ["offer_approved_by_user_id"],
            ["id"],
        )

    op.create_index(
        "ix_applications_offer_status", "job_applications", ["offer_status"]
    )


def downgrade() -> None:
    op.drop_index("ix_applications_offer_status", table_name="job_applications")
    with op.batch_alter_table("job_applications") as batch:
        batch.drop_constraint("fk_job_applications_offer_approved_by", type_="foreignkey")
        batch.drop_constraint("fk_job_applications_offer_submitted_by", type_="foreignkey")
        batch.drop_column("candidate_response_notes")
        batch.drop_column("candidate_response_at")
        batch.drop_column("candidate_response")
        batch.drop_column("offer_sent_at")
        batch.drop_column("offer_approval_notes")
        batch.drop_column("offer_approved_by_user_id")
        batch.drop_column("offer_approved_at")
        batch.drop_column("offer_submitted_by_user_id")
        batch.drop_column("offer_submitted_at")
        batch.drop_column("salary_override_approved")
        batch.drop_column("offer_additional_terms")
        batch.drop_column("offer_pdf_generated_at")
        batch.drop_column("offer_pdf_url")
        batch.drop_column("offer_status")
