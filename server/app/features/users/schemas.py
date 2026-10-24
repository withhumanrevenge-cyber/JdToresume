"""What the API returns about users (never the database row itself: backend-standards §2)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # can be built straight from a UserRow

    id: uuid.UUID
    email: str
    created_at: datetime
