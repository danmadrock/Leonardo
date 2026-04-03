"""add idempotency keys for task submission

Revision ID: 0003_task_idempotency
Revises: 0002_expand_pipeline_persistence
Create Date: 2026-04-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_task_idempotency"
down_revision = "0002_expand_pipeline_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("idempotency_key", sa.String(length=128), nullable=True))
    op.add_column("tasks", sa.Column("request_fingerprint", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_tasks_idempotency_key", "tasks", ["idempotency_key"])


def downgrade() -> None:
    op.drop_constraint("uq_tasks_idempotency_key", "tasks", type_="unique")
    op.drop_column("tasks", "request_fingerprint")
    op.drop_column("tasks", "idempotency_key")