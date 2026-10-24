"""Part 1: the API skeleton (settings, request ids, error format, logging)."""

from __future__ import annotations

import io
import logging
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import NotFoundError
from app.core import logging as app_logging
from app.core.logging import flush_logs, redact
from app.main import create_app


class Payload(BaseModel):
    email: str
    years: int


def make_app(**overrides) -> FastAPI:
    # _env_file=None: tests never read a developer's local .env
    return create_app(Settings(_env_file=None, **{"environment": "test", **overrides}))


@pytest.fixture
def client() -> TestClient:
    app = make_app()

    @app.get("/boom/not-found")
    async def not_found():
        raise NotFoundError("Application not found", details={"id": "a-1"})

    @app.post("/boom/validate")
    async def validate(payload: Payload):
        return payload

    @app.get("/boom/crash")
    async def crash():
        raise RuntimeError("secret internal detail")

    return TestClient(app, raise_server_exceptions=False)


def test_health_reports_version_and_environment(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0", "environment": "test"}


def test_every_response_carries_a_request_id(client):
    generated = client.get("/health").headers["x-request-id"]
    assert len(generated) == 32  # uuid4 hex
    assert client.get("/health", headers={"X-Request-ID": "trace-12345678"}).headers["x-request-id"] == "trace-12345678"
    # Unsafe ids are replaced, not echoed back.
    assert client.get("/health", headers={"X-Request-ID": "<script>"}).headers["x-request-id"] != "<script>"


def test_domain_error_uses_the_standard_shape(client):
    response = client.get("/boom/not-found")
    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "Application not found", "details": {"id": "a-1"}}


def test_validation_error_names_fields_but_never_echoes_values(client):
    response = client.post("/boom/validate", json={"email": "jordan@example.com", "years": "many"})
    body = response.json()
    assert response.status_code == 422 and body["code"] == "validation_error"
    assert body["details"]["errors"][0]["field"] == "body.years"
    assert "jordan@example.com" not in response.text and "many" not in response.text


def test_unknown_route_and_crash_use_the_standard_shape(client):
    assert client.get("/nope").json()["code"] == "not_found"
    crash = client.get("/boom/crash")
    assert crash.status_code == 500
    assert crash.json() == {"code": "internal_error", "message": "Something went wrong on our side"}
    assert "secret internal detail" not in crash.text


def test_docs_are_hidden_in_production():
    assert TestClient(make_app()).get("/docs").status_code == 200
    production = make_app(environment="production", auth_mode="jwks",
                          auth_jwks_url="https://app.example.com/api/auth/jwks", auth_issuer="https://app.example.com")
    assert TestClient(production).get("/docs").status_code == 404


def test_a_slow_log_output_never_slows_down_a_request():
    make_app()

    class SlowOutput(io.StringIO):  # e.g. a backed-up container stdout
        def write(self, text: str) -> int:
            time.sleep(0.2)
            return super().write(text)

    output = SlowOutput()
    app_logging._listener.handlers[0].setStream(output)
    started = time.perf_counter()
    for _ in range(5):
        logging.getLogger("test").info("hello")
    assert time.perf_counter() - started < 0.1  # 5 writes x 0.2 s happen on the background thread
    flush_logs()
    assert output.getvalue().count("hello") == 5


def test_logs_mask_personal_data(capsys):
    assert redact("mail jordan@example.com or call +1 555-014-2233") == "mail [email] or call [phone]"
    assert redact("GET /health -> 200 in 3 ms") == "GET /health -> 200 in 3 ms"
    make_app()  # installs our JSON log handler on stderr
    logging.getLogger("test").info("user %s signed up", "priya@example.com")
    flush_logs()  # records are written by a background thread; wait for it
    line = capsys.readouterr().err.strip().splitlines()[-1]
    assert '"message": "user [email] signed up"' in line and "priya@example.com" not in line
