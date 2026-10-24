"""Job links: one canonical form per job, so the same posting always maps to the same cache entry.

"https://Boards.Greenhouse.io/acme/jobs/123/?utm_source=x&gh_src=y#apply"
    -> "https://boards.greenhouse.io/acme/jobs/123"
"""

from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MAX_URL_LENGTH = 2000
# Query parameters that only say where a click came from; they never change which job is shown.
_TRACKING_PARAMS = {"gh_src", "ref", "referrer", "source", "src", "trk", "trkid", "lever-source", "lever-origin",
                    "fbclid", "gclid", "mc_cid", "mc_eid"}


class InvalidJobUrl(ValueError):
    """The text isn't a usable web address."""


def canonicalize(raw: str) -> str:
    raw = raw.strip()
    if not raw or len(raw) > MAX_URL_LENGTH:
        raise InvalidJobUrl("That doesn't look like a job link")
    if "://" not in raw:
        raw = "https://" + raw  # people often paste "jobs.lever.co/acme/123" without the scheme

    parts = urlsplit(raw)
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise InvalidJobUrl("Job links must start with http:// or https://")
    if parts.username or parts.password:
        raise InvalidJobUrl("Job links can't contain a username or password")
    try:
        port = parts.port
    except ValueError as exc:
        raise InvalidJobUrl("That link has an invalid port") from exc

    host = parts.hostname.lower().rstrip(".")
    netloc = host if port in (None, 80, 443) else f"{host}:{port}"
    query = urlencode(sorted(
        (key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_PARAMS and not key.lower().startswith("utm_")
    ))
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))  # the #fragment is dropped


def url_hash(canonical_url: str) -> str:
    """Fixed-length key for the cache index."""
    return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()
