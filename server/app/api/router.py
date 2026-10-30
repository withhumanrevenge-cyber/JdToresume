"""Collects every route of the API in one place.

Each feature has its own router (app/features/<feature>/router.py); add one line here per feature, under /v1.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api import health
from app.features.applications.router import router as applications_router
from app.features.billing.router import router as billing_router
from app.features.data_export.router import router as export_router
from app.features.generation.router import router as generation_router
from app.features.jobs.router import router as jobs_router
from app.features.profiles.router import router as profiles_router
from app.features.rendering.router import router as rendering_router
from app.features.scans.router import router as scans_router
from app.features.users.router import router as users_router

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(users_router)  # /v1/me
v1_router.include_router(billing_router)  # /v1/me/plan
v1_router.include_router(export_router)  # /v1/me/export
v1_router.include_router(profiles_router)  # /v1/profile
v1_router.include_router(jobs_router)  # /v1/jobs
v1_router.include_router(scans_router)  # /v1/scans
v1_router.include_router(applications_router)  # /v1/applications
v1_router.include_router(generation_router)  # /v1/applications/{id}/generate
v1_router.include_router(rendering_router)  # /v1/applications/{id}/files/..., /v1/applications/{id}/ats-check

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(v1_router)
