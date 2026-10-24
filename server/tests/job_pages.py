"""Sample job pages and feeds, shaped like the real public APIs, plus a fake network to serve them."""

from __future__ import annotations

from collections.abc import Callable

import httpx

from app.features.jobs.ingestion.fetch import SafeFetcher

GREENHOUSE_URL = "https://boards.greenhouse.io/kestrelpay/jobs/4012345"
GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/kestrelpay/jobs/4012345"
GREENHOUSE_JOB = {
    "id": 4012345,
    "title": "Backend Engineer, Payments",
    "company_name": "Kestrel Pay",
    "location": {"name": "Remote (US)"},
    # Greenhouse sends its HTML entity-escaped.
    "content": "&lt;p&gt;We move money for 3,000 merchants.&lt;/p&gt;&lt;h3&gt;Requirements&lt;/h3&gt;"
               "&lt;ul&gt;&lt;li&gt;5+ years of Go&lt;/li&gt;&lt;li&gt;Kafka&lt;/li&gt;&lt;/ul&gt;",
}

LEVER_URL = "https://jobs.lever.co/northwind/5f1e2d3c-aaaa-bbbb-cccc-1234567890ab"
LEVER_API = "https://api.lever.co/v0/postings/northwind/5f1e2d3c-aaaa-bbbb-cccc-1234567890ab"
LEVER_JOB = {
    "text": "Data Analyst",
    "categories": {"location": "Bengaluru", "team": "Analytics", "commitment": "Full-time"},
    "descriptionPlain": "Help our ops team make sense of 2M shipments a month.",
    "lists": [{"text": "Requirements", "content": "<li>SQL</li><li>Power BI</li>"}],
    "additionalPlain": "Hybrid, 3 days in office.",
}

ASHBY_URL = "https://jobs.ashbyhq.com/contoso/abc-123"
ASHBY_API = "https://api.ashbyhq.com/posting-api/job-board/contoso"
ASHBY_BOARD = {"jobs": [
    {"id": "zzz-999", "title": "Other job", "descriptionPlain": "Not this one."},
    {"id": "abc-123", "title": "Product Designer", "location": "Pune", "employmentType": "FullTime",
     "isRemote": False, "descriptionPlain": "Design the onboarding flow for 40k new users a month."},
]}

CAREERS_URL = "https://careers.contoso.example/jobs/sre"
CAREERS_PAGE = """<html><head><title>SRE at Contoso</title>
<script type="application/ld+json">{"@context": "https://schema.org", "@graph": [
  {"@type": "Organization", "name": "Contoso"},
  {"@type": "JobPosting", "title": "Site Reliability Engineer",
   "hiringOrganization": {"@type": "Organization", "name": "Contoso"},
   "jobLocation": {"@type": "Place", "address": {"addressLocality": "Austin", "addressRegion": "TX", "addressCountry": "US"}},
   "employmentType": "FULL_TIME",
   "baseSalary": {"currency": "USD", "value": {"minValue": 150000, "maxValue": 180000, "unitText": "YEAR"}},
   "description": "&lt;p&gt;Keep 99.95% uptime.&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Terraform&lt;/li&gt;&lt;/ul&gt;"}
]}</script></head>
<body><nav>Home | Careers</nav><main><h1>Site Reliability Engineer</h1><p>Apply now</p></main></body></html>"""

PLAIN_URL = "https://jobs.fabrikam.example/listing/42"
PLAIN_PAGE = ("<html><body><nav>Menu</nav><main><h1>QA Engineer</h1>"
              + "".join(f"<p>Responsibility number {i}: test the release pipeline carefully.</p>" for i in range(12))
              + "</main><footer>© Fabrikam</footer><script>track()</script></body></html>")

LOGIN_WALL_URL = "https://jobs.tinyco.example/view/7"
LOGIN_WALL_PAGE = "<html><body><p>Please sign in to continue.</p></body></html>"

PUBLIC_IP = "93.184.216.34"


def fake_network(routes: dict[str, httpx.Response | Callable[[httpx.Request], httpx.Response]],
                 seen: list[str] | None = None) -> httpx.MockTransport:
    """Serve `routes` by exact URL; anything else is a 404. Records requested URLs in `seen`."""

    def handle(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if seen is not None:
            seen.append(url)
        route = routes.get(url)
        if route is None:
            return httpx.Response(404)
        return route(request) if callable(route) else route

    return httpx.MockTransport(handle)


def fake_dns(overrides: dict[str, str] | None = None):
    """Every host resolves to a public address unless listed in `overrides`."""

    async def resolve(host: str) -> list[str]:
        return [(overrides or {}).get(host, PUBLIC_IP)]

    return resolve


def job_site_fetcher(seen: list[str] | None = None) -> SafeFetcher:
    """A fetcher whose 'internet' contains the sample pages and feeds above."""
    routes = {
        GREENHOUSE_API: httpx.Response(200, json=GREENHOUSE_JOB),
        LEVER_API: httpx.Response(200, json=LEVER_JOB),
        ASHBY_API: httpx.Response(200, json=ASHBY_BOARD),
        CAREERS_URL: httpx.Response(200, text=CAREERS_PAGE, headers={"content-type": "text/html"}),
        PLAIN_URL: httpx.Response(200, text=PLAIN_PAGE, headers={"content-type": "text/html"}),
        LOGIN_WALL_URL: httpx.Response(200, text=LOGIN_WALL_PAGE, headers={"content-type": "text/html"}),
    }
    return SafeFetcher(transport=fake_network(routes, seen), resolve=fake_dns())

