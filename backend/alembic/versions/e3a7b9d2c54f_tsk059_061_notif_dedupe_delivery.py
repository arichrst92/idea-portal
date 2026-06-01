"""TSK-059 + TSK-061: notifications dedupe_key + delivery audit columns.

Revision ID: e3a7b9d2c54f
Revises: d6f9c2e8b94a
Create Date: 2026-05-31 19:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "e3a7b9d2c54f"
down_revision: str | Sequence[str] | None = "d6f9c2e8b94a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("notifications") as batch:
        # TSK-059
        batch.add_column(sa.Column("dedupe_key", sa.String(length=200), nullable=True))
        # TSK-061
        batch.add_column(
            sa.Column(
                "delivery_status",
                sa.String(length=20),
                nullable=False,
                server_default="DELIVERED",
            )
        )
        batch.add_column(
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(sa.Column("error_message", sa.Text(), nullable=True))

    op.create_index(
        "ix_notifications_dedupe_key", "notifications", ["dedupe_key"], unique=False
    )
    op.create_index(
        "ix_notifications_dedupe_user",
        "notifications",
        ["user_id", "dedupe_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_dedupe_user", table_name="notifications")
    op.drop_index("ix_notifications_dedupe_key", table_name="notifications")
    with op.batch_alter_table("notifications") as batch:
        batch.drop_column("error_message")
        batch.drop_column("last_attempt_at")
        batch.drop_column("retry_count")
        batch.drop_column("delivery_status")
        batch.drop_column("dedupe_key")
