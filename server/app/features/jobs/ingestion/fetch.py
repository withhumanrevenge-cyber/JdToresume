"""Fetching job pages safely from our servers.

The URL comes from a user, so the fetcher must never become a way into our own network (SSRF):
- only http/https on the standard ports, and no username/password in the URL;
- every hostname is resolved first and refused if it points anywhere non-public (private ranges, loopback,
  link-local such as the cloud metadata address 169.254.169.254, multicast, reserved);
- redirects are followed by hand (at most 3) so every hop gets the same check;
- hard limits: 10 seconds, 3 MB, and no cookies kept between fetches;
- ordinary web pages (not the public ATS feeds) are fetched only if the site's robots.txt allows us.

In production this code also runs inside the isolated fetcher service, whose network rules block private ranges
(ARCHITECTURE §5), so these checks are the first line of defence, not the only one.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

USER_AGENT = "CreatorJobReader/0.1 (+https://example.com/job-reader)"
ROBOTS_AGENT = "CreatorJobReader"
TIMEOUT_SECONDS = 10.0
MAX_BYTES = 3 * 1024 * 1024
MAX_REDIRECTS = 3
_MAX_CACHED_ROBOTS = 1000

Resolver = Callable[[str], Awaitable[list[str]]]


class FetchError(Exception):
    """A page couldn't be fetched. The message is safe to show to the user."""


@dataclass(frozen=True)
class Page:
    url: str  # final URL, after redirects
    content_type: str
    text: str


async def resolve_with_dns(host: str) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


class SafeFetcher:
    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None, resolve: Resolver = resolve_with_dns):
        # `transport` and `resolve` are replaceable so tests can fake the network and DNS.
        self._transport = transport
        self._resolve = resolve
        self._robots: dict[str, RobotFileParser] = {}

    async def get_json(self, url: str) -> Any:
        page = await self._get(url, accept="application/json")
        try:
            return json.loads(page.text)
        except ValueError as exc:
            raise FetchError("The job feed returned something we couldn't read") from exc

    async def get_page(self, url: str) -> Page:
        if not await self._robots_allow(url):
            raise FetchError("This site asks automated readers not to fetch its pages. Paste the job text instead.")
        return await self._get(url, accept="text/html,application/xhtml+xml")

    # ----------------------------------------------------------------- internals

    async def _get(self, url: str, accept: str) -> Page:
        headers = {"User-Agent": USER_AGENT, "Accept": accept}
        # A fresh client per fetch: nothing (cookies, auth) carries over from one site to the next.
        async with httpx.AsyncClient(transport=self._transport, timeout=TIMEOUT_SECONDS, headers=headers,
                                     follow_redirects=False) as client:
            for _ in range(MAX_REDIRECTS + 1):
                await self._check_destination(url)
                try:
                    async with client.stream("GET", url) as response:
                        if response.is_redirect:
                            url = urljoin(url, response.headers.get("location", ""))
                            continue
                        if response.status_code >= 400:
                            raise FetchError(f"The page answered with an error (HTTP {response.status_code})")
                        body = await self._read_limited(response)
                        return Page(url=str(response.url), content_type=response.headers.get("content-type", ""),
                                    text=body.decode(response.encoding or "utf-8", errors="replace"))
                except httpx.HTTPError as exc:
                    raise FetchError("We couldn't reach that page") from exc
        raise FetchError("That link redirects too many times")

    async def _check_destination(self, url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise FetchError("Only http and https links can be read")
        if parts.username or parts.password or parts.port not in (None, 80, 443):
            raise FetchError("That link points somewhere we don't fetch from")
        host = parts.hostname
        try:
            addresses = [str(ipaddress.ip_address(host))]  # the URL already uses an IP address
        except ValueError:
            try:
                addresses = await self._resolve(host)
            except OSError as exc:
                raise FetchError("We couldn't find that website") from exc
        if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
            raise FetchError("That link doesn't point to a public website")

    @staticmethod
    async def _read_limited(response: httpx.Response) -> bytes:
        chunks, size = [], 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > MAX_BYTES:
                raise FetchError("That page is too large to read")
            chunks.append(chunk)
        return b"".join(chunks)

    async def _robots_allow(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        rules = self._robots.get(origin)
        if rules is None:
            rules = RobotFileParser()
            try:
                rules.parse((await self._get(origin + "/robots.txt", accept="text/plain")).text.splitlines())
            except FetchError:
                rules.parse([])  # no robots.txt (or it can't be read): nothing is disallowed
            if len(self._robots) >= _MAX_CACHED_ROBOTS:
                self._robots.clear()
            self._robots[origin] = rules
        return rules.can_fetch(ROBOTS_AGENT, url)
