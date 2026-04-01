"""expand task and report persistence for pipeline execution

Revision ID: 0002_expand_pipeline_persistence
Revises: 0001_initial_schema
Create Date: 2026-03-31
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_expand_pipeline_persistence"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    task_stage = sa.Enum("planning", "search", "analysis", "report", "done", "error", name="taskstage")
    task_stage.create(op.get_bind(), checkfirst=True)

    op.add_column("tasks", sa.Column("stage", task_stage, nullable=False, server_default="planning"))
    op.add_column("tasks", sa.Column("selected_sources", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")))
    op.add_column("tasks", sa.Column("max_papers", sa.Integer(), nullable=False, server_default="50"))
    op.add_column("tasks", sa.Column("max_iterations", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("tasks", sa.Column("iterations_used", sa.Integer(), nullable=False, server_default="0"))

    op.add_column("tasks", sa.Column("progress_subtasks_total", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("tasks", sa.Column("progress_subtasks_completed", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("tasks", sa.Column("progress_papers_collected", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("tasks", sa.Column("progress_findings_generated", sa.Integer(), nullable=False, server_default="0"))

    op.add_column("tasks", sa.Column("graph_state_snapshot_ref", sa.String(length=512), nullable=True))
    op.add_column("tasks", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("reports", sa.Column("structured_report_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")))
    op.add_column("reports", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))

    op.alter_column("tasks", "stage", server_default=None)
    op.alter_column("tasks", "selected_sources", server_default=None)
    op.alter_column("tasks", "max_papers", server_default=None)
    op.alter_column("tasks", "max_iterations", server_default=None)
    op.alter_column("tasks", "iterations_used", server_default=None)
    op.alter_column("tasks", "progress_subtasks_total", server_default=None)
    op.alter_column("tasks", "progress_subtasks_completed", server_default=None)
    op.alter_column("tasks", "progress_papers_collected", server_default=None)
    op.alter_column("tasks", "progress_findings_generated", server_default=None)
    op.alter_column("reports", "structured_report_json", server_default=None)
    op.alter_column("reports", "updated_at", server_default=None)


def downgrade() -> None:
    op.drop_column("reports", "updated_at")
    op.drop_column("reports", "structured_report_json")

    op.drop_column("tasks", "completed_at")
    op.drop_column("tasks", "started_at")
    op.drop_column("tasks", "graph_state_snapshot_ref")
    op.drop_column("tasks", "progress_findings_generated")
    op.drop_column("tasks", "progress_papers_collected")
    op.drop_column("tasks", "progress_subtasks_completed")
    op.drop_column("tasks", "progress_subtasks_total")
    op.drop_column("tasks", "iterations_used")
    op.drop_column("tasks", "max_iterations")
    op.drop_column("tasks", "max_papers")
    op.drop_column("tasks", "selected_sources")
    op.drop_column("tasks", "stage")

    sa.Enum(name="taskstage").drop(op.get_bind(), checkfirst=True)
