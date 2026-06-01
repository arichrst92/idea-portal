"""TSK-040: Employee.welcome_seen_at for welcome page tracking.

Revision ID: a4d7e9f1c628
Revises: f5b8c3a7e21d
Create Date: 2026-06-01 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "a4d7e9f1c628"
down_revision: str | Sequence[str] | None = "f5b8c3a7e21d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("employees") as batch:
        batch.add_column(
            sa.Column("welcome_seen_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("employees") as batch:
        batch.drop_column("welcome_seen_at")
