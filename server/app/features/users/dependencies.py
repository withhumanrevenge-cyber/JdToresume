"""FastAPI dependencies other features use to get the signed-in user.

Any route that needs a signed-in user declares `user: CurrentUser`. That single line verifies the token,
creates the user on their first request, and returns their `UserRow`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.core.auth import Principal, get_principal
from app.core.db import SessionDep
from app.features.users.models import UserRow
from app.features.users.service import UserService


def get_user_service(session: SessionDep) -> UserService:
    return UserService(session)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


async def get_current_user(principal: Annotated[Principal, Depends(get_principal)], users: UserServiceDep) -> UserRow:
    return await users.get_or_create(principal)


CurrentUser = Annotated[UserRow, Depends(get_current_user)]
