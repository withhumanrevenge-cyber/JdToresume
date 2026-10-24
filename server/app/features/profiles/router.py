"""Profile endpoints: upload a resume, read and edit the career profile, read and edit contact details."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status

from app.features.profiles.dependencies import ProfileServiceDep
from app.features.profiles.schemas import ContactIn, ContactOut, ProfileOut, ProfileUpdateIn, ResumeImportOut
from app.features.profiles.service import MAX_UPLOAD_BYTES
from app.features.users.dependencies import CurrentUser
from app.llm.dependencies import LLMDep

router = APIRouter(prefix="/profile", tags=["profile"])


@router.post(
    "/resume",
    response_model=ResumeImportOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a resume (PDF, TXT or MD, up to 5 MB) and turn it into a new profile version",
)
async def upload_resume(
    user: CurrentUser,
    profiles: ProfileServiceDep,
    llm: LLMDep,
    file: Annotated[UploadFile, File(description="The resume file")],
) -> ResumeImportOut:
    data = await file.read(MAX_UPLOAD_BYTES + 1)  # one byte over the limit is enough to know it's too big
    return await profiles.import_resume(user, file.filename or "", data, llm)


@router.get("", response_model=ProfileOut, summary="My latest profile version")
async def read_profile(user: CurrentUser, profiles: ProfileServiceDep) -> ProfileOut:
    return await profiles.get_profile(user)


@router.put("", response_model=ProfileOut, summary="Save an edited profile as a new version")
async def save_profile(user: CurrentUser, profiles: ProfileServiceDep, body: ProfileUpdateIn) -> ProfileOut:
    return await profiles.save_profile(user, body.base_version, body.profile)


@router.get("/contact", response_model=ContactOut, summary="My contact details")
async def read_contact(user: CurrentUser, profiles: ProfileServiceDep) -> ContactOut:
    return await profiles.get_contact(user)


@router.put("/contact", response_model=ContactOut, summary="Create or replace my contact details")
async def save_contact(user: CurrentUser, profiles: ProfileServiceDep, body: ContactIn) -> ContactOut:
    return await profiles.save_contact(user, body)
