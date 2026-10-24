"""Database table for users.

Naming: classes ending in `Row` are database tables. Services and the API work with Pydantic models instead
(DTO separation, backend-standards §2); repositories convert between the two.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, created_at_column


class UserRow(Base):
    """One person using Tailor.

    Sign-in is handled by the auth provider (Better Auth in the web app). We store its stable user id
    (`auth_subject`, the JWT `sub` claim) and create the row the first time that person calls the API.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    auth_subject: Mapped[str] = mapped_column(String(255), unique=True)
    email: Mapped[str] = mapped_column(String(320))
    created_at: Mapped[datetime] = created_at_column()

    __table_args__ = (
        # One account per email address, whatever its capitalisation (backend-standards §6).
        Index("uq_users_email_lower", text("lower(email)"), unique=True),
    )
