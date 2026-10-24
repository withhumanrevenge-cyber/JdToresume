"""Part 5: reading job links (no database, no real network)."""

from __future__ import annotations

import httpx
import pytest

from app.features.jobs.ingestion.ats import find_ats_feed
from app.features.jobs.ingestion.fetch import MAX_BYTES, FetchError, SafeFetcher
from app.features.jobs.ingestion.html import find_job_posting, html_to_text
from app.features.jobs.ingestion.reader import read_job_from_url
from app.features.jobs.policy import client_only_site
from app.features.jobs.urls import InvalidJobUrl, canonicalize, url_hash
from server.tests import job_pages as pages
from server.tests.job_pages import fake_dns, fake_network


# --------------------------------------------------------------------------- canonical links

def test_the_same_job_link_always_has_the_same_canonical_form():
    messy = "HTTPS://Boards.Greenhouse.io/kestrelpay/jobs/4012345/?utm_source=linkedin&gh_src=abc#apply"
    assert canonicalize(messy) == "https://boards.greenhouse.io/kestrelpay/jobs/4012345"
    assert canonicalize("jobs.lever.co/northwind/x?b=2&a=1") == "https://jobs.lever.co/northwind/x?a=1&b=2"
    assert url_hash(canonicalize(messy)) == url_hash(pages.GREENHOUSE_URL)


@pytest.mark.parametrize("bad", ["", "ftp://example.com/job", "https://user:pass@example.com/job", "https://"])
def test_unusable_links_are_rejected(bad):
    with pytest.raises(InvalidJobUrl):
        canonicalize(bad)


# --------------------------------------------------------------------------- no-scraping policy

@pytest.mark.parametrize(("host", "site"), [
    ("www.linkedin.com", "LinkedIn"), ("lnkd.in", "LinkedIn"), ("in.indeed.com", "Indeed"),
    ("indeed.co.uk", "Indeed"), ("www.naukri.com", "Naukri"), ("www.glassdoor.co.in", "Glassdoor"),
    ("wellfound.com", "Wellfound"),
])
def test_client_only_sites_are_recognised(host, site):
    assert client_only_site(host) == site


@pytest.mark.parametrize("host", ["boards.greenhouse.io", "indeed.greenhouse.io", "careers.linkedinlearning.example",
                                  "jobs.lever.co", "naukri.example.com"])
def test_other_sites_are_allowed(host):
    assert client_only_site(host) is None


# --------------------------------------------------------------------------- public ATS feeds

def test_ats_job_links_map_to_their_public_feeds():
    assert find_ats_feed(pages.GREENHOUSE_URL).api_url == pages.GREENHOUSE_API
    assert find_ats_feed("https://boards.greenhouse.io/embed/job_app?for=kestrelpay&token=4012345").api_url == pages.GREENHOUSE_API
    assert find_ats_feed(pages.LEVER_URL).api_url == pages.LEVER_API
    assert find_ats_feed("https://jobs.eu.lever.co/acme/123").api_url == "https://api.eu.lever.co/v0/postings/acme/123"
    assert find_ats_feed(pages.ASHBY_URL).api_url == pages.ASHBY_API
    assert find_ats_feed(pages.CAREERS_URL) is None


@pytest.mark.anyio
@pytest.mark.parametrize(("url", "vendor", "expected"), [
    (pages.GREENHOUSE_URL, "greenhouse", ["Title: Backend Engineer, Payments", "Company: Kestrel Pay",
                                          "Location: Remote (US)", "- 5+ years of Go", "- Kafka"]),
    (pages.LEVER_URL, "lever", ["Title: Data Analyst", "Location: Bengaluru", "Team: Analytics",
                                "Requirements:", "- SQL", "- Power BI", "Hybrid, 3 days in office."]),
    (pages.ASHBY_URL, "ashby", ["Title: Product Designer", "Location: Pune", "40k new users"]),
])
async def test_ats_feeds_become_readable_text(url, vendor, expected):
    raw = await read_job_from_url(pages.job_site_fetcher(), url)
    assert (raw.source, raw.ats_vendor) == ("ats_feed", vendor)
    for snippet in expected:
        assert snippet in raw.text
    assert "&lt;" not in raw.text and "<li>" not in raw.text and "Not this one" not in raw.text


# --------------------------------------------------------------------------- embedded job data and page text

@pytest.mark.anyio
async def test_embedded_job_data_wins_over_page_text():
    raw = await read_job_from_url(pages.job_site_fetcher(), pages.CAREERS_URL)
    assert raw.source == "embedded_data"
    for snippet in ("Title: Site Reliability Engineer", "Company: Contoso", "Location: Austin, TX, US",
                    "Salary: USD 150000–180000 per year", "Keep 99.95% uptime.", "- Terraform"):
        assert snippet in raw.text


@pytest.mark.anyio
async def test_page_text_is_the_fallback_and_skips_menus_and_scripts():
    raw = await read_job_from_url(pages.job_site_fetcher(), pages.PLAIN_URL)
    assert raw.source == "page_text"
    assert "QA Engineer" in raw.text and "Menu" not in raw.text and "track()" not in raw.text


@pytest.mark.anyio
async def test_a_page_without_a_job_description_is_refused():
    with pytest.raises(FetchError, match="couldn't find a job description"):
        await read_job_from_url(pages.job_site_fetcher(), pages.LOGIN_WALL_URL)


def test_html_helpers():
    assert html_to_text("<p>One</p><ul><li>Two</li></ul><script>x()</script>") == "One\n- Two"
    assert find_job_posting("<script type='application/ld+json'>{broken</script>") is None


# --------------------------------------------------------------------------- the safe fetcher (SSRF and limits)

def page(text: str = "ok", status: int = 200, **headers: str) -> httpx.Response:
    return httpx.Response(status, text=text, headers=headers)


@pytest.mark.anyio
@pytest.mark.parametrize(("url", "dns", "message"), [
    ("https://intranet.example/jobs", {"intranet.example": "10.0.0.5"}, "public website"),
    ("http://169.254.169.254/latest/meta-data", {}, "public website"),  # the cloud metadata address
    ("http://localhost/admin", {"localhost": "127.0.0.1"}, "public website"),
    ("https://example.com:8443/jobs", {}, "don't fetch from"),
    ("file:///etc/passwd", {}, "Only http and https"),
])
async def test_fetcher_refuses_anything_that_is_not_a_public_website(url, dns, message):
    fetcher = SafeFetcher(transport=fake_network({url: page()}), resolve=fake_dns(dns))
    with pytest.raises(FetchError, match=message):
        await fetcher.get_json(url)


@pytest.mark.anyio
async def test_every_redirect_hop_is_checked_too():
    routes = {"https://jobs.example/apply": page(status=302, location="http://internal.example/admin")}
    fetcher = SafeFetcher(transport=fake_network(routes), resolve=fake_dns({"internal.example": "192.168.1.10"}))
    with pytest.raises(FetchError, match="public website"):
        await fetcher.get_json("https://jobs.example/apply")


@pytest.mark.anyio
async def test_redirect_loops_and_oversized_pages_are_cut_off():
    loop = {"https://a.example/x": page(status=302, location="https://a.example/x")}
    with pytest.raises(FetchError, match="too many times"):
        await SafeFetcher(transport=fake_network(loop), resolve=fake_dns()).get_json("https://a.example/x")

    huge = {"https://a.example/big": httpx.Response(200, content=b"a" * (MAX_BYTES + 1))}
    with pytest.raises(FetchError, match="too large"):
        await SafeFetcher(transport=fake_network(huge), resolve=fake_dns()).get_json("https://a.example/big")


@pytest.mark.anyio
async def test_robots_txt_is_respected_for_pages_but_not_needed_for_public_feeds():
    seen: list[str] = []
    routes = {
        "https://jobs.example/robots.txt": page("User-agent: *\nDisallow: /private/"),
        "https://jobs.example/private/1": page("<p>secret</p>"),
        "https://jobs.example/open/1": page("<p>hello</p>"),
    }
    fetcher = SafeFetcher(transport=fake_network(routes, seen), resolve=fake_dns())

    with pytest.raises(FetchError, match="asks automated readers"):
        await fetcher.get_page("https://jobs.example/private/1")
    assert (await fetcher.get_page("https://jobs.example/open/1")).text == "<p>hello</p>"
    assert seen.count("https://jobs.example/robots.txt") == 1  # cached per site
    assert "https://jobs.example/private/1" not in seen  # never requested


@pytest.mark.anyio
async def test_http_errors_become_readable_messages():
    fetcher = SafeFetcher(transport=fake_network({}), resolve=fake_dns())
    with pytest.raises(FetchError, match="HTTP 404"):
        await fetcher.get_json("https://jobs.example/gone")
