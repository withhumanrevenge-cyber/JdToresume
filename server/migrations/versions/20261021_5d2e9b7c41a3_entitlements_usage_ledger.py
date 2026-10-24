"""Plans and usage: entitlements (plan, expiry, Deep credits) and the usage ledger (one row per pack started).

Revision ID: 5d2e9b7c41a3
Revises: 43cccb8862f3
Created: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5d2e9b7c41a3"
down_revision: str | None = "43cccb8862f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "entitlements",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("plan", sa.String(20), server_default="free", nullable=False),
        sa.Column("plan_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deep_credits", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", name="pk_entitlements"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_entitlements_user_id_users", ondelete="CASCADE"),
        # Short name on purpose: the naming convention turns it into ck_entitlements_deep_credits_not_negative.
        sa.CheckConstraint("deep_credits >= 0", name="deep_credits_not_negative"),
    )

    # A run's usage row outlives the run (SET NULL), so deleting an application never gives packs back.
    op.create_table(
        "usage_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("paid_with", sa.String(20), nullable=False),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_usage_ledger"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_usage_ledger_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["generation_runs.id"], name="fk_usage_ledger_run_id_generation_runs",
                                ondelete="SET NULL"),
    )
    op.create_index("ix_usage_ledger_user_id_created_at", "usage_ledger", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_usage_ledger_user_id_created_at", table_name="usage_ledger")
    op.drop_table("usage_ledger")
    op.drop_table("entitlements")
