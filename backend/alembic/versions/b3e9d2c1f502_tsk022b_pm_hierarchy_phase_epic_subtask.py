"""TSK-022B: PM hierarchy refactor — phase/epic/subtask/comments.

Changes:
- Drop project_milestones (replaced by project_phases)
- Create project_phases
- Create project_epics
- Alter project_tasks: add epic_id, slug, story_points; drop milestone_id
- Create project_subtasks
- Create project_task_comments
- Create project_subtask_comments
- Alter projects: add task_slug_counter
- Add FK invoices.trigger_phase_id → project_phases.id (deferred from TSK-022C)

Revision ID: b3e9d2c1f502
Revises: a7c2f5e8b401
Create Date: 2026-05-29 03:45:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "b3e9d2c1f502"
down_revision: str | Sequence[str] | None = "a7c2f5e8b401"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ─── 1. Drop project_milestones (data hilang — dev env) ─────────────
    # Pertama drop FK dari project_tasks.milestone_id
    op.drop_column("project_tasks", "milestone_id")
    # Hapus tabel milestone
    op.drop_index(
        op.f("ix_project_milestones_project_id"), table_name="project_milestones"
    )
    op.drop_table("project_milestones")

    # ─── 2. Add task_slug_counter ke projects ──────────────────────────
    op.add_column(
        "projects",
        sa.Column("task_slug_counter", sa.Integer(), nullable=False, server_default="0"),
    )

    # ─── 3. Create project_phases ───────────────────────────────────────
    op.create_table(
        "project_phases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PLANNED"),
        sa.Column(
            "progress_pct", sa.Numeric(precision=5, scale=2), nullable=False, server_default="0"
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_project_phases_project_id"), "project_phases", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_project_phases_deleted_at"), "project_phases", ["deleted_at"], unique=False
    )

    # ─── 4. Create project_epics ────────────────────────────────────────
    op.create_table(
        "project_epics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("phase_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="PLANNED"),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["phase_id"], ["project_phases.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_project_epics_phase_id"), "project_epics", ["phase_id"], unique=False)
    op.create_index(
        op.f("ix_project_epics_project_id"), "project_epics", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_project_epics_deleted_at"), "project_epics", ["deleted_at"], unique=False
    )

    # ─── 5. Alter project_tasks: add epic_id, slug, story_points ───────
    op.add_column(
        "project_tasks", sa.Column("epic_id", sa.Uuid(), nullable=True)
    )
    op.add_column(
        "project_tasks",
        sa.Column("slug", sa.String(length=30), nullable=False, server_default=""),
    )
    op.add_column(
        "project_tasks", sa.Column("story_points", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_project_tasks_epic_id", "project_tasks", "project_epics",
        ["epic_id"], ["id"],
    )
    op.create_index(op.f("ix_project_tasks_epic_id"), "project_tasks", ["epic_id"], unique=False)
    op.create_index(op.f("ix_project_tasks_slug"), "project_tasks", ["slug"], unique=False)

    # ─── 6. Create project_subtasks ────────────────────────────────────
    op.create_table(
        "project_subtasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("assignee_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="BACKLOG"),
        sa.Column("story_points", sa.Integer(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["project_tasks.id"]),
        sa.ForeignKeyConstraint(["assignee_id"], ["employees.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_project_subtasks_task_id"), "project_subtasks", ["task_id"], unique=False
    )
    op.create_index(
        op.f("ix_project_subtasks_slug"), "project_subtasks", ["slug"], unique=False
    )
    op.create_index(
        op.f("ix_project_subtasks_deleted_at"), "project_subtasks", ["deleted_at"], unique=False
    )

    # ─── 7. Create project_task_comments ───────────────────────────────
    op.create_table(
        "project_task_comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["project_tasks.id"]),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_project_task_comments_task_id"), "project_task_comments", ["task_id"],
        unique=False,
    )

    # ─── 8. Create project_subtask_comments ────────────────────────────
    op.create_table(
        "project_subtask_comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subtask_id", sa.Uuid(), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["subtask_id"], ["project_subtasks.id"]),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_project_subtask_comments_subtask_id"),
        "project_subtask_comments", ["subtask_id"], unique=False,
    )

    # ─── 9. Add FK invoices.trigger_phase_id → project_phases.id ───────
    op.create_foreign_key(
        "fk_invoices_trigger_phase_id", "invoices", "project_phases",
        ["trigger_phase_id"], ["id"],
    )


def downgrade() -> None:
    # Drop FK invoices.trigger_phase_id
    op.drop_constraint("fk_invoices_trigger_phase_id", "invoices", type_="foreignkey")

    # Drop project_subtask_comments
    op.drop_index(
        op.f("ix_project_subtask_comments_subtask_id"), table_name="project_subtask_comments"
    )
    op.drop_table("project_subtask_comments")

    # Drop project_task_comments
    op.drop_index(
        op.f("ix_project_task_comments_task_id"), table_name="project_task_comments"
    )
    op.drop_table("project_task_comments")

    # Drop project_subtasks
    op.drop_index(op.f("ix_project_subtasks_deleted_at"), table_name="project_subtasks")
    op.drop_index(op.f("ix_project_subtasks_slug"), table_name="project_subtasks")
    op.drop_index(op.f("ix_project_subtasks_task_id"), table_name="project_subtasks")
    op.drop_table("project_subtasks")

    # Revert project_tasks
    op.drop_index(op.f("ix_project_tasks_slug"), table_name="project_tasks")
    op.drop_index(op.f("ix_project_tasks_epic_id"), table_name="project_tasks")
    op.drop_constraint("fk_project_tasks_epic_id", "project_tasks", type_="foreignkey")
    op.drop_column("project_tasks", "story_points")
    op.drop_column("project_tasks", "slug")
    op.drop_column("project_tasks", "epic_id")

    # Drop project_epics
    op.drop_index(op.f("ix_project_epics_deleted_at"), table_name="project_epics")
    op.drop_index(op.f("ix_project_epics_project_id"), table_name="project_epics")
    op.drop_index(op.f("ix_project_epics_phase_id"), table_name="project_epics")
    op.drop_table("project_epics")

    # Drop project_phases
    op.drop_index(op.f("ix_project_phases_deleted_at"), table_name="project_phases")
    op.drop_index(op.f("ix_project_phases_project_id"), table_name="project_phases")
    op.drop_table("project_phases")

    # Remove projects.task_slug_counter
    op.drop_column("projects", "task_slug_counter")

    # Recreate project_milestones
    op.create_table(
        "project_milestones",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("completed_at", sa.Date(), nullable=True),
        sa.Column(
            "progress_pct", sa.Numeric(precision=5, scale=2), nullable=False, server_default="0"
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_project_milestones_project_id"), "project_milestones", ["project_id"],
        unique=False,
    )

    # Re-add milestone_id ke project_tasks
    op.add_column(
        "project_tasks", sa.Column("milestone_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        "fk_project_tasks_milestone_id", "project_tasks", "project_milestones",
        ["milestone_id"], ["id"],
    )
