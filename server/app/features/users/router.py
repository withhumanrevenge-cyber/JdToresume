"""Account endpoints: who am I, and delete everything about me."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.features.users.dependencies import CurrentUser, UserServiceDep
from app.features.users.schemas import UserOut

router = APIRouter(prefix="/me", tags=["account"])


@router.get("", response_model=UserOut, summary="The signed-in user (created on their first request)")
async def read_me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT, summary="Delete my account and all my data")
async def delete_me(user: CurrentUser, users: UserServiceDep) -> None:
    await users.delete_account(user)
