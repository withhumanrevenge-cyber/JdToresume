"""The FastAPI application.

Run locally (Windows, from the repo root):
    .venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
Then open http://localhost:8000/docs for the interactive API docs.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from groq import AsyncGroq

from app.api.dev import router as dev_router
from app.api.router import api_router
from app.core.auth import build_verifier
from app.core.config import Settings, get_settings
from app.core.db import Database
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestIdMiddleware
from app.features.jobs.ingestion.fetch import SafeFetcher


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build a fully configured app. Tests call this with their own Settings."""
    settings = settings or get_settings()
    configure_logging(settings.log_level, json_output=settings.json_logs)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Startup. Nothing here connects yet, so a down database or Groq doesn't block startup.
        app.state.db = Database(settings.database_url, echo=settings.database_echo)
        app.state.groq = (
            AsyncGroq(api_key=settings.groq_api_key.get_secret_value(), max_retries=4, timeout=180)
            if settings.groq_api_key
            else None  # AI routes answer 503 until a key is configured
        )
        app.state.llm_slots = asyncio.Semaphore(settings.llm_max_concurrency)
        app.state.fetcher = SafeFetcher()  # reads job links safely (app/features/jobs/ingestion/fetch.py)
        yield
        # Shutdown: close pooled connections.
        await app.state.db.close()
        if app.state.groq is not None:
            await app.state.groq.close()

    app = FastAPI(
        lifespan=lifespan,
        title=settings.app_name,
        version=settings.app_version,
        # Interactive docs are handy everywhere except production, where they'd advertise the whole API surface.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    # Checks sign-in tokens (app/core/auth.py). Creating it does no network calls; JWKS keys are fetched lazily.
    app.state.token_verifier = build_verifier(settings)

    # The middleware added last runs first. Request ids therefore wrap everything, including CORS.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        # Response headers the web app may read: downloads need the file name and the ATS check result.
        expose_headers=["X-Request-ID", "Content-Disposition", "X-ATS-Check"],
    )
    app.add_middleware(RequestIdMiddleware)

    register_error_handlers(app)
    app.include_router(api_router)
    if settings.auth_mode == "dev":  # passwordless local sign-in for the web app; never exists in staging/production
        app.include_router(dev_router, prefix="/v1")
    return app


app = create_app()
