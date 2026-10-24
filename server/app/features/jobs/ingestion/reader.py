"""Turn a job link into the posting's text, trying the most reliable source first (jd-ingestion skill §1):

1. a public ATS feed (Greenhouse, Lever, Ashby),
2. structured job data embedded in the page (schema.org JobPosting),
3. the page's readable text.

The headless-browser fallback for JavaScript-only pages arrives with the isolated fetcher service.
"""

from __future__ import annotations

from app.features.jobs.ingestion.ats import find_ats_feed
from app.features.jobs.ingestion.fetch import FetchError, SafeFetcher
from app.features.jobs.ingestion.html import find_job_posting, html_to_text, raw_job_from_posting
from app.features.jobs.ingestion.raw import RawJob

MIN_PAGE_TEXT_CHARS = 400  # shorter than this, a page is a login wall or a shell that needs JavaScript


async def read_job_from_url(fetcher: SafeFetcher, url: str) -> RawJob:
    feed = find_ats_feed(url)
    if feed is not None:
        return feed.parse(await fetcher.get_json(feed.api_url), feed.job_id)

    page = await fetcher.get_page(url)
    posting = find_job_posting(page.text)
    if posting is not None:
        return raw_job_from_posting(posting)

    text = html_to_text(page.text)
    if len(text) >= MIN_PAGE_TEXT_CHARS:
        return RawJob(text=text, source="page_text")
    raise FetchError("We couldn't find a job description on that page. Paste the job text instead.")
