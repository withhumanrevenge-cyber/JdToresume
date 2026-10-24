"""Checking sign-in tokens.

Every protected request carries `Authorization: Bearer <token>`. This module answers one question: is the token
genuine, and whose is it? It knows nothing about our database; turning the person into a `users` row is the users
feature's job (app/features/users/dependencies.py).

Two modes, chosen by `settings.auth_mode`:
- "jwks" (staging/production): the sign-in provider (Better Auth in the web app) signs tokens with its private key.
  We check the signature against its published public keys (the JWKS endpoint), plus expiry, issuer and audience.
- "dev" (local/test only): tokens signed with a shared secret and minted by `python -m app.cli.dev_token`, so the
  API can be used and tested before the web app exists. Settings refuse this mode in staging and production.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Protocol

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from app.core.config import Settings
from app.core.errors import UnauthorizedError

DEV_ISSUER = "tailor-dev"
_LEEWAY_SECONDS = 30  # tolerate small clock differences between servers
_REQUIRED_CLAIMS = ["exp", "iat", "sub", "iss", "aud"]
# Asymmetric algorithms only. Accepting HS256 here would let anyone holding the *public* key forge tokens.
_JWKS_ALGORITHMS = ["EdDSA", "ES256", "RS256"]


class Principal(BaseModel):
    """The signed-in person, as the token describes them."""

    model_config = ConfigDict(frozen=True)

    subject: str  # their stable id at the sign-in provider (the JWT `sub` claim)
    email: str


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> Principal: ...


def _principal_from(claims: dict[str, Any]) -> Principal:
    email = claims.get("email")
    if not isinstance(email, str) or "@" not in email:
        raise UnauthorizedError("The sign-in token has no email address")
    return Principal(subject=str(claims["sub"]), email=email)


class DevTokenVerifier:
    def __init__(self, secret: str, audience: str):
        self._secret = secret
        self._audience = audience

    async def verify(self, token: str) -> Principal:
        try:
            claims = jwt.decode(
                token, self._secret, algorithms=["HS256"], audience=self._audience, issuer=DEV_ISSUER,
                leeway=_LEEWAY_SECONDS, options={"require": _REQUIRED_CLAIMS},
            )
        except jwt.PyJWTError as exc:
            raise UnauthorizedError("Invalid or expired sign-in token") from exc
        return _principal_from(claims)


class JwksTokenVerifier:
    def __init__(self, jwks_url: str, issuer: str, audience: str, key_client: jwt.PyJWKClient | None = None):
        # The client caches the provider's public keys and refetches when it sees an unknown key id.
        self._keys = key_client or jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=3600, timeout=5)
        self._issuer = issuer
        self._audience = audience

    async def verify(self, token: str) -> Principal:
        try:
            # Finding the key may fetch the JWKS over the network, so it runs off the event loop.
            signing_key = await asyncio.to_thread(self._keys.get_signing_key_from_jwt, token)
            claims = jwt.decode(
                token, signing_key.key, algorithms=_JWKS_ALGORITHMS, audience=self._audience, issuer=self._issuer,
                leeway=_LEEWAY_SECONDS, options={"require": _REQUIRED_CLAIMS},
            )
        except jwt.PyJWTError as exc:
            raise UnauthorizedError("Invalid or expired sign-in token") from exc
        return _principal_from(claims)


def build_verifier(settings: Settings) -> TokenVerifier:
    if settings.auth_mode == "jwks":
        assert settings.auth_jwks_url and settings.auth_issuer  # guaranteed by Settings validation
        return JwksTokenVerifier(settings.auth_jwks_url, settings.auth_issuer, settings.auth_audience)
    return DevTokenVerifier(settings.auth_dev_secret.get_secret_value(), settings.auth_audience)


def mint_dev_token(
    secret: str, *, subject: str, email: str, audience: str = "tailor-api", ttl: timedelta = timedelta(hours=12)
) -> str:
    """A dev-mode token (local/test only). Real tokens come from the sign-in provider."""
    now = datetime.now(UTC)
    claims = {"sub": subject, "email": email, "iss": DEV_ISSUER, "aud": audience, "iat": now, "exp": now + ttl}
    return jwt.encode(claims, secret, algorithm="HS256")


# --------------------------------------------------------------------------- FastAPI dependency

_bearer = HTTPBearer(auto_error=False, description="Sign-in token from the web app (or app.cli.dev_token locally)")


def get_token_verifier(request: Request) -> TokenVerifier:
    return request.app.state.token_verifier


async def get_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
) -> Principal:
    if credentials is None:
        raise UnauthorizedError("Sign-in required: send an 'Authorization: Bearer <token>' header")
    return await verifier.verify(credentials.credentials)
