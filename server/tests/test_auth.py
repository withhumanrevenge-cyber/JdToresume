"""Part 3: sign-in token verification (no database needed)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.auth import DevTokenVerifier, JwksTokenVerifier, Principal, mint_dev_token
from app.core.config import Settings
from app.core.errors import UnauthorizedError
from app.main import create_app

SECRET = "unit-test-secret-0123456789abcdefgh"
ISSUER, AUDIENCE = "https://app.example.com", "tailor-api"


# --------------------------------------------------------------------------- dev tokens

@pytest.mark.anyio
async def test_dev_token_round_trip():
    token = mint_dev_token(SECRET, subject="dev|priya", email="priya@example.com")
    assert await DevTokenVerifier(SECRET, "tailor-api").verify(token) == Principal(subject="dev|priya", email="priya@example.com")


@pytest.mark.anyio
@pytest.mark.parametrize("token", [
    mint_dev_token(SECRET, subject="s", email="a@example.com", ttl=-timedelta(minutes=5)),        # expired
    mint_dev_token("another-secret-0123456789abcdefghij", subject="s", email="a@example.com"),  # wrong key
    mint_dev_token(SECRET, subject="s", email="a@example.com", audience="someone-else"),         # wrong audience
    "not-a-token",
])
async def test_bad_dev_tokens_are_rejected(token):
    with pytest.raises(UnauthorizedError):
        await DevTokenVerifier(SECRET, "tailor-api").verify(token)


@pytest.mark.anyio
async def test_token_without_email_is_rejected():
    now = datetime.now(UTC)
    claims = {"sub": "s", "iss": "tailor-dev", "aud": "tailor-api", "iat": now, "exp": now + timedelta(hours=1)}
    with pytest.raises(UnauthorizedError, match="no email"):
        await DevTokenVerifier(SECRET, "tailor-api").verify(jwt.encode(claims, SECRET, algorithm="HS256"))


# --------------------------------------------------------------------------- real-provider (JWKS) tokens

class FakeKeyClient:
    """Stands in for PyJWKClient: always returns our test public key instead of fetching the JWKS URL."""

    def __init__(self, public_key):
        jwk = jwt.algorithms.OKPAlgorithm.to_jwk(public_key, as_dict=True)
        self._key = jwt.PyJWK({**jwk, "kid": "k1", "alg": "EdDSA"})

    def get_signing_key_from_jwt(self, token: str) -> jwt.PyJWK:
        return self._key


def provider_token(private_key, **overrides) -> str:
    now = datetime.now(UTC)
    claims = {"sub": "user_123", "email": "priya@example.com", "iss": ISSUER, "aud": AUDIENCE,
              "iat": now, "exp": now + timedelta(minutes=15), **overrides}
    return jwt.encode(claims, private_key, algorithm="EdDSA", headers={"kid": "k1"})


@pytest.mark.anyio
async def test_jwks_verifier_accepts_the_providers_signature_only():
    provider_key, attacker_key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    verifier = JwksTokenVerifier("https://unused", ISSUER, AUDIENCE, key_client=FakeKeyClient(provider_key.public_key()))

    assert (await verifier.verify(provider_token(provider_key))).subject == "user_123"
    for bad in (provider_token(attacker_key), provider_token(provider_key, iss="https://evil.example.com")):
        with pytest.raises(UnauthorizedError):
            await verifier.verify(bad)


@pytest.mark.anyio
async def test_jwks_verifier_rejects_hs256_signed_with_the_public_key():
    # Classic "algorithm confusion" attack: sign with HS256 using the (public) key as the shared secret.
    provider_key = Ed25519PrivateKey.generate()
    public_pem = provider_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    now = int(datetime.now(UTC).timestamp())
    # PyJWT refuses to build this token, so assemble it by hand the way an attacker would.
    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()
    header = b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": "k1"}).encode())
    payload = b64(json.dumps({"sub": "admin", "email": "x@example.com", "iss": ISSUER, "aud": AUDIENCE,
                              "iat": now, "exp": now + 300}).encode())
    signature = b64(hmac.new(public_pem, f"{header}.{payload}".encode(), hashlib.sha256).digest())
    forged = f"{header}.{payload}.{signature}"

    verifier = JwksTokenVerifier("https://unused", ISSUER, AUDIENCE, key_client=FakeKeyClient(provider_key.public_key()))
    with pytest.raises(UnauthorizedError):
        await verifier.verify(forged)


# --------------------------------------------------------------------------- settings guard and HTTP behaviour

def test_dev_tokens_can_never_be_enabled_in_staging_or_production():
    for environment in ("staging", "production"):
        with pytest.raises(ValidationError, match="AUTH_MODE=dev"):
            Settings(_env_file=None, environment=environment, auth_mode="dev")
    with pytest.raises(ValidationError, match="AUTH_JWKS_URL"):
        Settings(_env_file=None, environment="production", auth_mode="jwks")


def test_missing_or_garbage_token_gives_401_with_bearer_challenge():
    client = TestClient(create_app(Settings(_env_file=None, environment="test")))
    for headers in ({}, {"Authorization": "Bearer nonsense"}, {"Authorization": "Basic dXNlcjpwYXNz"}):
        response = client.get("/v1/me", headers=headers)
        assert response.status_code == 401
        assert response.json()["code"] == "unauthorized"
        assert response.headers["www-authenticate"] == "Bearer"


# --------------------------------------------------------------------------- dev sign-in for the web app

@pytest.mark.anyio
async def test_dev_sign_in_gives_a_token_the_api_accepts():
    client = TestClient(create_app(Settings(_env_file=None, environment="test", auth_mode="dev", auth_dev_secret=SECRET)))

    response = client.post("/v1/dev/sign-in", json={"email": "Jordan@Example.com"})
    invalid = client.post("/v1/dev/sign-in", json={"email": "not-an-email"})

    assert response.status_code == 200
    principal = await DevTokenVerifier(SECRET, "tailor-api").verify(response.json()["token"])
    assert principal == Principal(subject="dev|jordan@example.com", email="Jordan@Example.com")  # same as the CLI
    assert invalid.status_code == 422


def test_dev_sign_in_does_not_exist_outside_dev_mode():
    settings = Settings(_env_file=None, environment="production", auth_mode="jwks",
                        auth_jwks_url="https://app.example.com/api/auth/jwks", auth_issuer=ISSUER)
    client = TestClient(create_app(settings))
    assert client.post("/v1/dev/sign-in", json={"email": "jordan@example.com"}).status_code == 404
