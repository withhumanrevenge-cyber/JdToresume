"""Part 2: database schema, migrations and the readiness check."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.features.profiles.models import CareerProfileRow, ContactDetailsRow
from app.features.users.models import UserRow
from app.llm.schemas import CareerProfile
from app.main import create_app

SAMPLE_PROFILE = json.loads((Path(__file__).parent / "fixtures" / "sample_profile.json").read_text(encoding="utf-8"))


async def add_user(session: AsyncSession, email: str = "priya@example.com", subject: str = "auth|priya") -> UserRow:
    user = UserRow(auth_subject=subject, email=email)
    session.add(user)
    await session.flush()  # sends the INSERT so user.id can be used by the rows that follow
    return user


@pytest.mark.anyio
async def test_profile_versions_are_append_only_and_the_latest_wins(db):
    first = CareerProfile.model_validate(SAMPLE_PROFILE)
    second = first.model_copy(update={"headline": "Senior Backend Engineer"})

    async with db.sessions() as session:
        user = await add_user(session)
        session.add_all([
            CareerProfileRow(user_id=user.id, version=1, data=first.model_dump(mode="json")),
            CareerProfileRow(user_id=user.id, version=2, data=second.model_dump(mode="json")),
        ])
        await session.commit()

        latest = await session.scalar(
            select(CareerProfileRow)
            .where(CareerProfileRow.user_id == user.id)
            .order_by(CareerProfileRow.version.desc())
            .limit(1)
        )

    assert latest.version == 2
    # JSONB round-trips into a valid CareerProfile.
    assert CareerProfile.model_validate(latest.data).headline == "Senior Backend Engineer"


@pytest.mark.anyio
async def test_the_same_profile_version_cannot_be_saved_twice(db):
    async with db.sessions() as session:
        user = await add_user(session)
        session.add_all([
            CareerProfileRow(user_id=user.id, version=1, data=SAMPLE_PROFILE),
            CareerProfileRow(user_id=user.id, version=1, data=SAMPLE_PROFILE),
        ])
        with pytest.raises(IntegrityError, match="uq_career_profiles_user_id_version"):
            await session.commit()


@pytest.mark.anyio
async def test_profile_version_must_be_positive(db):
    async with db.sessions() as session:
        user = await add_user(session)
        session.add(CareerProfileRow(user_id=user.id, version=0, data=SAMPLE_PROFILE))
        with pytest.raises(IntegrityError, match="ck_career_profiles_version_positive"):
            await session.commit()


@pytest.mark.anyio
async def test_email_is_unique_whatever_its_capitalisation(db):
    async with db.sessions() as session:
        await add_user(session, email="priya@example.com", subject="auth|1")
        with pytest.raises(IntegrityError, match="uq_users_email_lower"):
            await add_user(session, email="Priya@Example.COM", subject="auth|2")


@pytest.mark.anyio
async def test_deleting_a_user_deletes_their_contact_details_and_profiles(db):
    async with db.sessions() as session:
        user = await add_user(session)
        session.add_all([
            ContactDetailsRow(user_id=user.id, full_name="Priya Example", email="priya@example.com",
                              phone=None, city="Bengaluru", links=["github.com/priya-example"]),
            CareerProfileRow(user_id=user.id, version=1, data=SAMPLE_PROFILE),
        ])
        await session.commit()

        await session.execute(delete(UserRow).where(UserRow.id == user.id))
        await session.commit()

        remaining_contacts = await session.scalar(select(func.count()).select_from(ContactDetailsRow))
        remaining_profiles = await session.scalar(select(func.count()).select_from(CareerProfileRow))
    assert (remaining_contacts, remaining_profiles) == (0, 0)


@pytest.mark.anyio
async def test_contact_links_default_to_an_empty_list(db):
    async with db.sessions() as session:
        user = await add_user(session)
        session.add(ContactDetailsRow(user_id=user.id, full_name="Priya Example", email="priya@example.com",
                                      phone=None, city=None))
        await session.commit()
        contact = await session.get(ContactDetailsRow, user.id)
        await session.refresh(contact)
    assert contact.links == []
    assert isinstance(contact.user_id, uuid.UUID)


def test_migrations_downgrade_and_upgrade_cleanly_and_match_the_models(migrations):
    command.downgrade(migrations, "base")
    command.upgrade(migrations, "head")
    command.check(migrations)  # raises if the models and the migrations disagree


def test_readiness_reflects_the_database(migrated_test_db):
    up = create_app(Settings(_env_file=None, environment="test", database_url=migrated_test_db))
    with TestClient(up) as client:  # `with` runs startup/shutdown, which creates the connection pool
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}

    down = create_app(Settings(_env_file=None, environment="test",
                               database_url="postgresql+asyncpg://tailor:tailor@127.0.0.1:1/nothing"))
    with TestClient(down) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unreachable"}
