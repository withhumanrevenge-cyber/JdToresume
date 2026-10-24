"""Public job feeds of applicant tracking systems.

Greenhouse, Lever and Ashby publish every open job through public JSON feeds (no login, made for job boards).
When a link points at one of their job pages, we read the feed instead of the page: it's structured, fast and
exactly what these feeds are for.
"""

from __future__ import annotations

import html as html_lib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlsplit

from app.features.jobs.ingestion.fetch import FetchError
from app.features.jobs.ingestion.html import html_to_text
from app.features.jobs.ingestion.raw import RawJob, compose_text


@dataclass(frozen=True)
class AtsFeed:
    vendor: str
    api_url: str
    job_id: str
    parse: Callable[[Any, str], RawJob]  # (feed JSON, job id) -> RawJob


def find_ats_feed(url: str) -> AtsFeed | None:
    """The public feed for a Greenhouse, Lever or Ashby job link, or None for any other link."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    path = [segment for segment in parts.path.split("/") if segment]

    if host in ("boards.greenhouse.io", "job-boards.greenhouse.io", "boards.eu.greenhouse.io",
                "job-boards.eu.greenhouse.io"):
        query = parse_qs(parts.query)
        if len(path) >= 3 and path[1] == "jobs" and path[2].isdigit():  # /{board}/jobs/{id}
            board, job_id = path[0], path[2]
        elif path[:2] == ["embed", "job_app"] and query.get("for") and query.get("token"):  # embedded job links
            board, job_id = query["for"][0], query["token"][0]
        else:
            return None
        return AtsFeed("greenhouse", f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}", job_id,
                       _parse_greenhouse)

    if host in ("jobs.lever.co", "jobs.eu.lever.co") and len(path) >= 2:  # /{site}/{posting id}
        api_host = "api.eu.lever.co" if ".eu." in host else "api.lever.co"
        return AtsFeed("lever", f"https://{api_host}/v0/postings/{path[0]}/{path[1]}", path[1], _parse_lever)

    if host == "jobs.ashbyhq.com" and len(path) >= 2:  # /{board}/{job id}
        return AtsFeed("ashby", f"https://api.ashbyhq.com/posting-api/job-board/{path[0]}", path[1], _parse_ashby)

    return None


def _parse_greenhouse(data: Any, job_id: str) -> RawJob:
    try:
        body = html_to_text(html_lib.unescape(data.get("content") or ""))  # Greenhouse escapes its HTML
        text = compose_text(title=data["title"], company=data.get("company_name"),
                            location=(data.get("location") or {}).get("name"), body=body)
    except (KeyError, TypeError, AttributeError) as exc:
        raise FetchError("The Greenhouse feed returned an unexpected format") from exc
    return RawJob(text=text, source="ats_feed", ats_vendor="greenhouse")


def _parse_lever(data: Any, job_id: str) -> RawJob:
    try:
        categories = data.get("categories") or {}
        sections = [data.get("descriptionPlain") or html_to_text(data.get("description") or "")]
        for block in data.get("lists") or []:  # e.g. "Requirements", "Nice to have", each with HTML items
            sections.append(f"{block.get('text', '')}:\n{html_to_text(block.get('content') or '')}")
        sections.append(data.get("additionalPlain") or "")
        text = compose_text(title=data["text"], company=None, location=categories.get("location"),
                            body="\n\n".join(s for s in sections if s.strip()),
                            extra={"Team": categories.get("team"), "Employment type": categories.get("commitment")})
    except (KeyError, TypeError, AttributeError) as exc:
        raise FetchError("The Lever feed returned an unexpected format") from exc
    return RawJob(text=text, source="ats_feed", ats_vendor="lever")


def _parse_ashby(data: Any, job_id: str) -> RawJob:
    try:
        job = next((j for j in data.get("jobs") or [] if j.get("id") == job_id), None)
        if job is None:
            raise FetchError("This job is no longer listed on the company's job board")
        text = compose_text(title=job["title"], company=None, location=job.get("location"),
                            body=job.get("descriptionPlain") or html_to_text(job.get("descriptionHtml") or ""),
                            extra={"Employment type": job.get("employmentType"),
                                   "Remote": "yes" if job.get("isRemote") else None})
    except (KeyError, TypeError, AttributeError) as exc:
        raise FetchError("The Ashby feed returned an unexpected format") from exc
    return RawJob(text=text, source="ats_feed", ats_vendor="ashby")
