"""Account export endpoint: download everything we store about me as one JSON file."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.features.data_export.dependencies import ExportServiceDep
from app.features.data_export.schemas import AccountExport
from app.features.users.dependencies import CurrentUser

router = APIRouter(prefix="/me", tags=["account"])


@router.get("/export", response_model=AccountExport, summary="Download all my data as one JSON file")
async def export_my_data(user: CurrentUser, exports: ExportServiceDep, response: Response) -> AccountExport:
    export = await exports.export(user)
    response.headers["Content-Disposition"] = f'attachment; filename="account-export-{export.exported_at:%Y-%m-%d}.json"'
    response.headers["Cache-Control"] = "private, no-store"  # personal data: never kept by shared or browser caches
    return export
