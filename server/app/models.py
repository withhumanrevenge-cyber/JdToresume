"""Imports every table model so `Base.metadata` knows all tables.

Alembic (server/migrations/env.py) and the tests import this module. When a feature adds a models.py,
add one import line here; otherwise Alembic won't see its tables.
"""

from app.features.applications.models import ApplicationRow
from app.features.billing.models import EntitlementRow, UsageRow
from app.features.generation.models import ArtifactRow, GenerationRunRow
from app.features.jobs.models import JobRow
from app.features.profiles.models import CareerProfileRow, ContactDetailsRow
from app.features.users.models import UserRow
from app.llm.ledger import LlmCallRow

__all__ = [
    "ApplicationRow", "ArtifactRow", "CareerProfileRow", "ContactDetailsRow", "EntitlementRow", "GenerationRunRow",
    "JobRow", "LlmCallRow", "UsageRow", "UserRow",
]
