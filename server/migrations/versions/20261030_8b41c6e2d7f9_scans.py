"""Match scans: one row per free scan that called the AI.

Revision ID: 8b41c6e2d7f9
Revises: 5d2e9b7c41a3
Created: 2026-10-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "8b41c6e2d7f9"
down_revision: str | None = "5d2e9b7c41a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("result", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_scans"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_scans_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name="fk_scans_job_id_jobs", ondelete="CASCADE"),
    )
    op.create_index("ix_scans_user_id_created_at", "scans", ["user_id", "created_at"])
    op.create_index("ix_scans_user_id_job_id", "scans", ["user_id", "job_id"])


def downgrade() -> None:
    op.drop_index("ix_scans_user_id_job_id", table_name="scans")
    op.drop_index("ix_scans_user_id_created_at", table_name="scans")
    op.drop_table("scans")
