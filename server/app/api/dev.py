"""Local-development sign-in: trade an email for a dev token, so the web app can sign in without a real provider.

Mounted only when AUTH_MODE=dev, which the settings refuse in staging and production (app/core/config.py), so this
route doesn't exist there. Better Auth replaces it (ARCHITECTURE §12). Same token as `app.cli.dev_token`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.core.auth import mint_dev_token
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/dev", tags=["development"])

TOKEN_LIFETIME = timedelta(hours=12)


class DevSignInIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class DevSignInOut(BaseModel):
    token: str = Field(description="Send as 'Authorization: Bearer <token>'")
    expires_at: datetime


@router.post("/sign-in", response_model=DevSignInOut,
             summary="Development only: get a sign-in token for an email (no password)")
async def dev_sign_in(body: DevSignInIn, settings: Annotated[Settings, Depends(get_settings)]) -> DevSignInOut:
    token = mint_dev_token(
        settings.auth_dev_secret.get_secret_value(),
        subject=f"dev|{body.email.lower()}",
        email=body.email,
        audience=settings.auth_audience,
        ttl=TOKEN_LIFETIME,
    )
    return DevSignInOut(token=token, expires_at=datetime.now(UTC) + TOKEN_LIFETIME)
