"""Job postings: shared rows for public links, private rows for pasted text.

Revision ID: 1a8faef6c5a0
Revises: 10cfc50dc518
Created: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "1a8faef6c5a0"
down_revision: str | None = "10cfc50dc518"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=True),  # NULL = shared (read from a public link)
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("ats_vendor", sa.String(20), nullable=True),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("url_hash", sa.String(64), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("company", sa.String(300), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("spec", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_jobs"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], name="fk_jobs_owner_user_id_users", ondelete="CASCADE"),
    )
    # One shared row per public link.
    op.create_index("uq_jobs_shared_url_hash", "jobs", ["url_hash"], unique=True,
                    postgresql_where=sa.text("owner_user_id IS NULL"))
    # "Has this user already pasted this exact text?"
    op.create_index("ix_jobs_owner_content_hash", "jobs", ["owner_user_id", "content_hash"])


def downgrade() -> None:
    op.drop_index("ix_jobs_owner_content_hash", table_name="jobs")
    op.drop_index("uq_jobs_shared_url_hash", table_name="jobs")
    op.drop_table("jobs")
