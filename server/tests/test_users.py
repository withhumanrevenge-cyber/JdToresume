"""Part 3: automatic user creation, GET /v1/me and DELETE /v1/me (real database)."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import func, select

from app.core.auth import Principal
from app.features.profiles.models import CareerProfileRow, ContactDetailsRow
from app.features.users.models import UserRow
from app.features.users.service import UserService

pytestmark = pytest.mark.anyio


async def count(db, model) -> int:
    async with db.sessions() as session:
        return await session.scalar(select(func.count()).select_from(model))


async def test_first_request_creates_the_user_and_later_requests_reuse_it(client, sign_in, db):
    headers = sign_in("priya@example.com")
    first = await client.get("/v1/me", headers=headers)
    second = await client.get("/v1/me", headers=headers)

    assert first.status_code == 200
    assert first.json()["email"] == "priya@example.com"
    assert second.json()["id"] == first.json()["id"]
    assert await count(db, UserRow) == 1


async def test_delete_me_erases_the_user_and_everything_about_them(client, sign_in, db):
    headers = sign_in("priya@example.com")
    user_id = (await client.get("/v1/me", headers=headers)).json()["id"]
    async with db.sessions() as session:
        session.add_all([
            ContactDetailsRow(user_id=user_id, full_name="Priya Example", email="priya@example.com", phone=None, city=None),
            CareerProfileRow(user_id=user_id, version=1, data={"headline": "Backend engineer"}),
        ])
        await session.commit()

    response = await client.delete("/v1/me", headers=headers)

    assert response.status_code == 204 and response.content == b""
    assert (await count(db, UserRow), await count(db, ContactDetailsRow), await count(db, CareerProfileRow)) == (0, 0, 0)


async def test_same_email_from_a_different_sign_in_identity_is_a_conflict(client, sign_in):
    assert (await client.get("/v1/me", headers=sign_in("priya@example.com", subject="google|1"))).status_code == 200

    response = await client.get("/v1/me", headers=sign_in("Priya@Example.com", subject="email|2"))

    assert response.status_code == 409
    assert response.json()["code"] == "conflict"


async def test_simultaneous_first_requests_create_exactly_one_user(db):
    principal = Principal(subject="dev|race", email="race@example.com")

    async def first_request() -> str:
        async with db.sessions() as session:
            return str((await UserService(session).get_or_create(principal)).id)

    ids = await asyncio.gather(*(first_request() for _ in range(5)))

    assert len(set(ids)) == 1
    assert await count(db, UserRow) == 1
