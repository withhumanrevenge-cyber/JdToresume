"""Which job sites our servers must never fetch (CLAUDE.md non-negotiable #4, jd-ingestion skill §2).

These sites forbid automated access in their terms or need a login. Users paste the job text instead (and later,
the browser extension reads the page they are already looking at, on their click). Keep this list the single
source of truth: the jobs service checks it before any network call.
"""

from __future__ import annotations

import re

# Country variants such as indeed.co.uk, in.indeed.com or glassdoor.co.in are covered by the patterns.
_COUNTRY_TLD = r"(?:com|[a-z]{2}|co\.[a-z]{2}|com\.[a-z]{2})"
_CLIENT_ONLY_SITES: dict[str, re.Pattern[str]] = {
    "LinkedIn": re.compile(r"(?:^|\.)(?:linkedin\.com|lnkd\.in)$"),
    "Indeed": re.compile(rf"(?:^|\.)indeed\.{_COUNTRY_TLD}$"),
    "Naukri": re.compile(r"(?:^|\.)naukri\.com$"),
    "Glassdoor": re.compile(rf"(?:^|\.)glassdoor\.{_COUNTRY_TLD}$"),
    "Monster": re.compile(rf"(?:^|\.)monster\.{_COUNTRY_TLD}$"),
    "foundit": re.compile(r"(?:^|\.)foundit\.(?:in|com|sg|my)$"),
    "Instahyre": re.compile(r"(?:^|\.)instahyre\.com$"),
    "Wellfound": re.compile(r"(?:^|\.)wellfound\.com$"),
}


def client_only_site(host: str) -> str | None:
    """The site's display name if we must not fetch it (e.g. "LinkedIn"), otherwise None."""
    host = host.lower().rstrip(".")
    for name, pattern in _CLIENT_ONLY_SITES.items():
        if pattern.search(host):
            return name
    return None
