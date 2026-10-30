"""The cost ledger: one row for every AI call we pay for.

Rows hold no personal data (step, model, token counts, cost), so when an account is deleted they stay, with the
user link set to NULL, and cost accounting remains complete. `record_llm_calls` uses its own short database session
so the record is kept even when the request itself failed.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Literal

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, Database, created_at_column
from app.llm.client import LLMCall

logger = logging.getLogger(__name__)

Purpose = Literal["resume_parse", "job_extract", "generation", "scan"]


class LlmCallRow(Base):
    __tablename__ = "llm_calls"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("generation_runs.id", ondelete="SET NULL"))
    purpose: Mapped[str] = mapped_column(String(30))
    step: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(80))
    prompt_version: Mapped[str] = mapped_column(String(80))
    prompt_tokens: Mapped[int] = mapped_column(Integer)
    cached_tokens: Mapped[int] = mapped_column(Integer)
    completion_tokens: Mapped[int] = mapped_column(Integer)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float] = mapped_column(Numeric(12, 6, asdecimal=False))
    latency_ms: Mapped[int] = mapped_column(Integer)
    finish_reason: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = created_at_column()

    __table_args__ = (
        Index("ix_llm_calls_created_at", "created_at"),  # "what did we spend today?"
        Index("ix_llm_calls_user_id", "user_id"),  # "what does this user cost us?"
    )


async def record_llm_calls(
    database: Database,
    calls: Sequence[LLMCall],
    *,
    user_id: uuid.UUID | None,
    purpose: Purpose,
    run_id: uuid.UUID | None = None,
) -> None:
    """Save the calls. Never raises: a lost cost record is logged, but must not turn a success into an error."""
    if not calls:
        return
    rows = [
        LlmCallRow(user_id=user_id, run_id=run_id, purpose=purpose, step=call.step, model=call.model,
                   prompt_version=call.prompt_version, prompt_tokens=call.prompt_tokens,
                   cached_tokens=call.cached_tokens, completion_tokens=call.completion_tokens,
                   reasoning_tokens=call.reasoning_tokens, cost_usd=call.cost_usd, latency_ms=call.latency_ms,
                   finish_reason=call.finish_reason)
        for call in calls
    ]
    try:
        async with database.sessions() as session:
            session.add_all(rows)
            await session.commit()
    except Exception:
        logger.exception("Could not record %d %s LLM call(s); total $%.6f", len(rows), purpose,
                         sum(call.cost_usd for call in calls))
