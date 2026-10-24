"""Shared test fixtures.

Database tests use the `tailor_test` database in the local Docker Postgres (`docker compose up -d db`).
The schema is built once per test run by the real Alembic migrations (so migrations are tested too), and every
table is emptied after each test. If the database isn't running, database tests are skipped, not failed.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import httpx
import pytest
from alembic import command
from fastapi import FastAPI
from alembic.config import Config
from sqlalchemy import text

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.core.auth import mint_dev_token
from app.core.config import Settings
from app.core.db import Base, Database
from app.features.jobs.ingestion.fetch import SafeFetcher
from app.llm.client import GroqLLM
from app.llm.dependencies import get_llm
from app.main import create_app
from server.tests.fakes import FakeGroq
from server.tests.packs import ANSWERS

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://tailor:tailor@localhost:5433/tailor_test"
)
TEST_DEV_SECRET = "test-only-dev-secret-0123456789abcdef"


@pytest.fixture
def anyio_backend() -> str:
    """Async tests (marked @pytest.mark.anyio) run on asyncio."""
    return "asyncio"


def alembic_config(url: str = TEST_DATABASE_URL) -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["configure_logging"] = False  # keep test output clean
    return config


async def _is_reachable(url: str) -> bool:
    database = Database(url)
    try:
        return await database.is_reachable()
    finally:
        await database.close()


@pytest.fixture(scope="session")
def migrated_test_db() -> str:
    """The test database URL, with the schema rebuilt from the migrations."""
    if not asyncio.run(_is_reachable(TEST_DATABASE_URL)):
        if os.environ.get("REQUIRE_TEST_DATABASE") == "1":  # CI sets this: a missing database must fail, not skip
            pytest.fail(f"Test database not reachable at {TEST_DATABASE_URL} (REQUIRE_TEST_DATABASE=1)")
        pytest.skip("Test database not reachable. Start it with: docker compose up -d db")
    config = alembic_config()
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    return TEST_DATABASE_URL


@pytest.fixture
def migrations(migrated_test_db: str) -> Config:
    """Alembic config pointed at the test database, for tests that run migrations themselves."""
    return alembic_config(migrated_test_db)


@pytest.fixture
async def db(migrated_test_db: str) -> AsyncIterator[Database]:
    """A Database for one test; every table is emptied afterwards."""
    database = Database(migrated_test_db)
    yield database
    tables = ", ".join(table.name for table in Base.metadata.sorted_tables)
    async with database.engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {tables} CASCADE"))
    await database.close()


@pytest.fixture
def test_settings(migrated_test_db: str) -> Settings:
    return Settings(
        _env_file=None, environment="test", database_url=migrated_test_db,
        auth_mode="dev", auth_dev_secret=TEST_DEV_SECRET,
    )


@pytest.fixture
def api_app(db: Database, test_settings: Settings) -> FastAPI:
    """The real app wired to the test database. Tests can replace dependencies via `api_app.dependency_overrides`
    (e.g. the LLM, see test_profiles.py). There is no real Groq client: AI routes answer 503 unless overridden."""
    application = create_app(test_settings)
    # The in-process transport doesn't run startup, so set what startup would.
    application.state.db = db
    application.state.groq = None
    application.state.llm_slots = asyncio.Semaphore(4)
    application.state.fetcher = SafeFetcher(transport=httpx.MockTransport(_no_network))  # tests never go online
    return application


def _no_network(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"A test tried to fetch {request.url}; override get_fetcher with a fake network")


@pytest.fixture
def ai(api_app: FastAPI) -> FakeGroq:
    """A fake Groq that writes the sample application pack (tests/packs.py). Its `.requests` are what was sent."""
    fake = FakeGroq({kind: list(answers) for kind, answers in ANSWERS.items()})
    api_app.dependency_overrides[get_llm] = lambda: GroqLLM(client=fake)
    return fake


@pytest.fixture
async def client(api_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """An HTTP client for the app, sharing the test's database (so tests can check rows directly)."""
    transport = httpx.ASGITransport(app=api_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@pytest.fixture
def sign_in() -> Callable[..., dict[str, str]]:
    """`headers = sign_in("priya@example.com")` gives an Authorization header with a dev token."""

    def headers(email: str, subject: str | None = None) -> dict[str, str]:
        token = mint_dev_token(TEST_DEV_SECRET, subject=subject or f"dev|{email}", email=email)
        return {"Authorization": f"Bearer {token}"}

    return headers
