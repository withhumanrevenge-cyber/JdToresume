"""Part 8: plans, usage metering before every generate, GET /v1/me/plan, granting plans, and the account export.

Real test database, fake Groq.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select, update

import app.models  # noqa: F401  (registers every table)
from app.cli.grant import grant
from app.core.db import Base
from app.features.applications.models import ApplicationRow
from app.features.billing.models import EntitlementRow, UsageRow
from app.features.billing.plans import next_month, window_start
from app.features.billing.service import BillingService, UpgradeRequiredError
from app.features.data_export.service import EXPORTED_TABLES, NOT_PERSONAL_TABLES
from app.features.jobs.models import JobRow
from app.llm.client import GroqLLM
from app.llm.dependencies import get_llm
from server.tests.fakes import FailingGroq
from server.tests.packs import ANSWERS, CONTACT, JOB, JOB_TEXT, new_application


async def _generate(client, headers, application_id: str, mode: str | None = None):
    query = f"?mode={mode}" if mode else ""
    return await client.post(f"/v1/applications/{application_id}/generate{query}", headers=headers)


def _mode(response) -> str:
    """The mode the run actually used, from the first ("run") event of the stream."""
    first_event = response.text.split("\n\n")[0]
    data = next(line for line in first_event.splitlines() if line.startswith("data: "))
    return json.loads(data.removeprefix("data: "))["mode"]


async def _user_id(client, headers) -> uuid.UUID:
    return uuid.UUID((await client.get("/v1/me", headers=headers)).json()["id"])


def _when(value: str) -> datetime:
    return datetime.fromisoformat(value)


# --------------------------------------------------------------------------- windows

def test_months_are_calendar_months_in_utc():
    assert window_start("calendar_month", datetime(2026, 10, 21, 8, 30, tzinfo=UTC)) == datetime(2026, 10, 1, tzinfo=UTC)
    assert next_month(datetime(2026, 12, 15, 13, 0, tzinfo=UTC)) == datetime(2027, 1, 1, tzinfo=UTC)
    now = datetime(2026, 10, 21, tzinfo=UTC)
    assert window_start("rolling_7_days", now) == now - timedelta(days=7)


# --------------------------------------------------------------------------- the Free plan

@pytest.mark.anyio
async def test_a_new_user_is_on_free_with_one_deep_pack(client, sign_in):
    plan = (await client.get("/v1/me/plan", headers=sign_in("jordan@example.com"))).json()

    assert {k: plan[k] for k in ("plan", "expires_at", "deep_included", "deep_credits", "next_pack_mode")} == {
        "plan": "free", "expires_at": None, "deep_included": False, "deep_credits": 1, "next_pack_mode": "deep"}
    assert {k: plan["packs"][k] for k in ("used", "limit", "window")} == {"used": 0, "limit": 3, "window": "calendar_month"}
    assert _when(plan["packs"]["resets_at"]) == next_month(datetime.now(UTC))


@pytest.mark.anyio
async def test_free_is_one_deep_pack_then_three_quick_packs_a_month(client, sign_in, ai):
    headers = sign_in("jordan@example.com")
    application_id = await new_application(client, headers)

    modes = [_mode(await _generate(client, headers, application_id)) for _ in range(4)]
    fifth = await _generate(client, headers, application_id)
    plan = (await client.get("/v1/me/plan", headers=headers)).json()

    assert modes == ["deep", "quick", "quick", "quick"]
    assert (fifth.status_code, fifth.json()["code"]) == (402, "quota_exceeded")
    assert _when(fifth.json()["details"]["resets_at"]) == next_month(datetime.now(UTC))
    assert (plan["packs"]["used"], plan["deep_credits"], plan["next_pack_mode"]) == (3, 0, None)


@pytest.mark.anyio
async def test_deep_needs_a_credit_or_a_paid_plan(client, sign_in, ai):
    headers = sign_in("jordan@example.com")
    application_id = await new_application(client, headers)

    assert _mode(await _generate(client, headers, application_id, "deep")) == "deep"  # the sign-up credit
    refused = await _generate(client, headers, application_id, "deep")
    quick = await _generate(client, headers, application_id, "quick")

    assert (refused.status_code, refused.json()["code"]) == (402, "upgrade_required")
    assert _mode(quick) == "quick"


@pytest.mark.anyio
@pytest.mark.parametrize(("failing_step", "finished", "given_back"), [
    ("MatchReport", [], True),
    ("TailoredResume", ["match_report", "cover_letter", "outreach"], True),  # everything but the resume
    ("CoverLetter", ["match_report", "resume", "outreach"], False),
], ids=["nothing-delivered", "all-but-the-resume", "resume-delivered"])
async def test_a_run_without_the_resume_gives_its_pack_back(api_app, client, sign_in, db, failing_step, finished,
                                                            given_back):
    headers = sign_in("jordan@example.com")
    # The delay makes the order deterministic: the other parallel pieces finish before the failing step fails.
    fake = FailingGroq({kind: list(answers) for kind, answers in ANSWERS.items()}, fail=failing_step, fail_after=0.3)
    api_app.dependency_overrides[get_llm] = lambda: GroqLLM(client=fake)
    application_id = await new_application(client, headers)

    response = await _generate(client, headers, application_id)  # uses the Deep credit
    plan = (await client.get("/v1/me/plan", headers=headers)).json()
    async with db.sessions() as session:
        usage = (await session.scalars(select(UsageRow))).one()

    assert response.status_code == 200 and "event: error" in response.text
    assert all(f"event: {kind}\n" in response.text for kind in finished)  # finished pieces are kept either way
    assert plan["deep_credits"] == (1 if given_back else 0)
    assert (usage.refunded_at is not None) == given_back
    assert ("It didn't use up a pack." in response.text) == given_back  # and the person is told


@pytest.mark.anyio
async def test_two_generates_at_once_cannot_spend_the_same_credit(client, sign_in, db):
    user_id = await _user_id(client, sign_in("jordan@example.com"))
    async with db.sessions() as session:  # an existing row: creating it would already make the two take turns
        session.add(EntitlementRow(user_id=user_id, deep_credits=1))
        await session.commit()

    async def attempt() -> str:
        async with db.sessions() as session:
            try:
                await BillingService(session).reserve_pack(user_id, "deep", datetime.now(UTC))
            except UpgradeRequiredError:
                return "refused"
            await asyncio.sleep(0.2)  # keep the transaction open so the other attempt overlaps it
            await session.commit()
            return "spent"

    results = await asyncio.gather(attempt(), attempt())

    async with db.sessions() as session:
        credits = await session.scalar(select(EntitlementRow.deep_credits).where(EntitlementRow.user_id == user_id))
        rows = await session.scalar(select(func.count()).select_from(UsageRow))
    assert sorted(results) == ["refused", "spent"]  # without the row lock both would read 1 credit and spend it
    assert (credits, rows) == (0, 1)


# --------------------------------------------------------------------------- paid plans and granting

@pytest.mark.anyio
async def test_paid_plans_include_deep_up_to_the_fair_use_cap(client, sign_in, ai, db):
    headers = sign_in("jordan@example.com")
    user_id = await _user_id(client, headers)
    async with db.sessions() as session:
        await BillingService(session).grant_plan(user_id, "sprint", datetime.now(UTC))
        await session.commit()
    application_id = await new_application(client, headers)

    plan = (await client.get("/v1/me/plan", headers=headers)).json()
    first = await _generate(client, headers, application_id)
    async with db.sessions() as session:  # 99 more packs this week: the 100-pack fair-use cap is reached
        session.add_all(UsageRow(user_id=user_id, mode="deep", paid_with="plan") for _ in range(99))
        await session.commit()
    capped = await _generate(client, headers, application_id)
    after = (await client.get("/v1/me/plan", headers=headers)).json()

    assert (plan["plan"], plan["deep_included"], plan["packs"]["limit"], plan["packs"]["window"]) == (
        "sprint", True, 100, "rolling_7_days")
    assert abs(_when(plan["expires_at"]) - (datetime.now(UTC) + timedelta(days=7))) < timedelta(minutes=1)
    assert _mode(first) == "deep" and after["deep_credits"] == 1  # Deep came with the plan, not from the credit
    assert (capped.status_code, capped.json()["code"]) == (429, "fair_use_limit")
    assert int(capped.headers["retry-after"]) > 6 * 24 * 3600  # the oldest pack leaves the window in ~7 days


@pytest.mark.anyio
async def test_buying_again_extends_the_plan_and_an_expired_plan_is_free_again(client, sign_in, db):
    headers = sign_in("jordan@example.com")
    user_id = await _user_id(client, headers)
    async with db.sessions() as session:
        billing = BillingService(session)
        await billing.grant_plan(user_id, "sprint", datetime.now(UTC))
        twice = await billing.grant_plan(user_id, "sprint", datetime.now(UTC))
        await session.commit()
    assert abs(twice.plan_expires_at - (datetime.now(UTC) + timedelta(days=14))) < timedelta(minutes=1)

    async with db.sessions() as session:
        await session.execute(update(EntitlementRow).values(plan_expires_at=datetime.now(UTC) - timedelta(seconds=1)))
        await session.commit()
    plan = (await client.get("/v1/me/plan", headers=headers)).json()

    assert (plan["plan"], plan["expires_at"], plan["packs"]["limit"]) == ("free", None, 3)


@pytest.mark.anyio
async def test_the_grant_cli(client, sign_in, db):
    headers = sign_in("jordan@example.com")
    await client.get("/v1/me", headers=headers)

    message = await grant(db, "Jordan@Example.com", "pro_quarter", 10)
    missing = await grant(db, "nobody@example.com", "sprint", None)
    plan = (await client.get("/v1/me/plan", headers=headers)).json()

    assert message.startswith("Jordan@Example.com: Pro (quarter) until ") and "10 Deep credits (balance 11)" in message
    assert missing == "No user with email nobody@example.com: they need to sign in once first"
    assert (plan["plan"], plan["deep_credits"]) == ("pro_quarter", 11)


@pytest.mark.anyio
async def test_deleting_an_application_never_gives_packs_back(client, sign_in, ai, db):
    headers = sign_in("jordan@example.com")
    application_id = await new_application(client, headers)
    await _generate(client, headers, application_id)  # Deep credit
    await _generate(client, headers, application_id)  # 1 of 3 free packs

    async with db.sessions() as session:
        await session.execute(delete(ApplicationRow).where(ApplicationRow.id == uuid.UUID(application_id)))
        await session.commit()
        run_links = list(await session.scalars(select(UsageRow.run_id)))
    plan = (await client.get("/v1/me/plan", headers=headers)).json()

    assert run_links == [None, None]  # the runs are gone, the ledger rows stay
    assert (plan["packs"]["used"], plan["deep_credits"]) == (1, 0)


@pytest.mark.anyio
async def test_deleting_my_account_deletes_my_plan_and_usage(client, sign_in, ai, db):
    headers = sign_in("jordan@example.com")
    await _generate(client, headers, await new_application(client, headers))

    assert (await client.delete("/v1/me", headers=headers)).status_code == 204
    async with db.sessions() as session:
        left = [await session.scalar(select(func.count()).select_from(table)) for table in (EntitlementRow, UsageRow)]
    assert left == [0, 0]


# --------------------------------------------------------------------------- account export

@pytest.mark.anyio
async def test_the_export_holds_everything_about_me_and_nothing_about_anyone_else(client, sign_in, ai):
    jordan, priya = sign_in("jordan@example.com"), sign_in("priya@example.com")
    assert (await client.put("/v1/profile/contact", headers=jordan, json=CONTACT)).status_code == 200
    await _generate(client, jordan, await new_application(client, jordan))
    await _generate(client, priya, await new_application(client, priya))

    response = await client.get("/v1/me/export", headers=jordan)
    data = response.json()

    assert response.status_code == 200 and response.headers["cache-control"] == "private, no-store"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="account-export-{datetime.now(UTC):%Y-%m-%d}.json"')
    assert data["format_version"] == 1 and data["account"]["email"] == "jordan@example.com"
    assert data["contact_details"]["full_name"] == "Jordan Rivera"
    assert [p["version"] for p in data["profile_versions"]] == [1]
    [job] = data["jobs"]
    assert (job["added_by_you"], job["text"], job["company"]) == (True, JOB_TEXT.strip(), JOB["company"])
    [application] = data["applications"]
    [run] = application["runs"]
    assert application["job_id"] == job["id"]
    assert sorted(run["pieces"]) == ["cover_letter", "match_report", "outreach", "resume"]
    assert data["plan"] == {"plan": "free", "plan_expires_at": None, "deep_credits": 0}
    assert [(u["paid_with"], u["run_id"]) for u in data["usage"]] == [("deep_credit", run["id"])]
    assert {c["purpose"] for c in data["ai_calls"]} == {"job_extract", "generation"} and all(c["model"] for c in data["ai_calls"])
    assert "priya" not in response.text  # nothing from another account
    assert "cost_usd" not in response.text and "prompt_version" not in response.text  # our figures, not theirs


@pytest.mark.anyio
async def test_a_shared_job_is_exported_without_its_text(client, sign_in, db):
    headers = sign_in("jordan@example.com")
    url = "https://boards.greenhouse.io/example/jobs/1"
    async with db.sessions() as session:
        job = JobRow(owner_user_id=None, source="ats_feed", canonical_url=url, url_hash=hashlib.sha256(url.encode()).hexdigest(),
                     content_hash="0" * 64, title=JOB["title"], company=JOB["company"], raw_text="public text", spec=JOB)
        session.add(job)
        await session.commit()
    await client.post("/v1/applications", headers=headers, json={"job_id": str(job.id)})

    [exported] = (await client.get("/v1/me/export", headers=headers)).json()["jobs"]

    assert (exported["added_by_you"], exported["text"], exported["url"]) == (False, None, url)


def test_every_table_is_exported_or_marked_not_personal():
    """Fails when a new table appears: decide whether its rows belong in the export (data_export/service.py)."""
    assert set(Base.metadata.tables) == EXPORTED_TABLES | NOT_PERSONAL_TABLES
    assert not EXPORTED_TABLES & NOT_PERSONAL_TABLES
