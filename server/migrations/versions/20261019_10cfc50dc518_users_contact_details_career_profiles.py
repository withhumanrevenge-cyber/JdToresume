"""Users, contact details and versioned career profiles.

Revision ID: 10cfc50dc518
Revises: (first migration)
Created: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "10cfc50dc518"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("auth_subject", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("auth_subject", name="uq_users_auth_subject"),
    )
    # One account per email, case-insensitive.
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)

    op.create_table(
        "contact_details",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("city", sa.String(120), nullable=True),
        sa.Column("links", JSONB(), server_default="[]", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", name="pk_contact_details"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_contact_details_user_id_users", ondelete="CASCADE"),
    )

    op.create_table(
        "career_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("data", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_career_profiles"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_career_profiles_user_id_users", ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "version", name="uq_career_profiles_user_id_version"),
        # Short name on purpose: the naming convention in app/core/db.py turns it into ck_career_profiles_version_positive.
        sa.CheckConstraint("version >= 1", name="version_positive"),
    )


def downgrade() -> None:
    op.drop_table("career_profiles")
    op.drop_table("contact_details")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_table("users")
