"""Applications, generation runs, their artifacts, and the LLM cost ledger.

Revision ID: 43cccb8862f3
Revises: 1a8faef6c5a0
Created: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "43cccb8862f3"
down_revision: str | None = "1a8faef6c5a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_applications"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_applications_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name="fk_applications_job_id_jobs", ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "job_id", name="uq_applications_user_id_job_id"),
    )
    op.create_index("ix_applications_user_id_created_at", "applications", ["user_id", "created_at"])

    op.create_table(
        "generation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("error", sa.String(40), nullable=True),
        sa.Column("cost_usd", sa.Numeric(12, 6), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_generation_runs"),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"],
                                name="fk_generation_runs_application_id_applications", ondelete="CASCADE"),
    )
    op.create_index("ix_generation_runs_application_id_started_at", "generation_runs", ["application_id", "started_at"])

    op.create_table(
        "artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_artifacts"),
        sa.ForeignKeyConstraint(["run_id"], ["generation_runs.id"], name="fk_artifacts_run_id_generation_runs",
                                ondelete="CASCADE"),
        sa.UniqueConstraint("run_id", "kind", name="uq_artifacts_run_id_kind"),
    )

    # The cost ledger keeps its rows when a user or run is deleted (the links become NULL): no personal data in it.
    op.create_table(
        "llm_calls",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("step", sa.String(40), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("prompt_version", sa.String(80), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("cached_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("finish_reason", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_llm_calls"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_llm_calls_user_id_users", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["generation_runs.id"], name="fk_llm_calls_run_id_generation_runs",
                                ondelete="SET NULL"),
    )
    op.create_index("ix_llm_calls_created_at", "llm_calls", ["created_at"])
    op.create_index("ix_llm_calls_user_id", "llm_calls", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_calls_user_id", table_name="llm_calls")
    op.drop_index("ix_llm_calls_created_at", table_name="llm_calls")
    op.drop_table("llm_calls")
    op.drop_table("artifacts")
    op.drop_index("ix_generation_runs_application_id_started_at", table_name="generation_runs")
    op.drop_table("generation_runs")
    op.drop_index("ix_applications_user_id_created_at", table_name="applications")
    op.drop_table("applications")
