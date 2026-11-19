"""Shared HTTP helpers."""

from __future__ import annotations

import asyncio
import datetime as dt
import email.utils
import json
import os
import re
import time

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
TIMEOUT = httpx.Timeout(20.0, connect=10.0)

_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


# Politeness limits. They apply per host and across tool calls, so an agent firing a burst of
# searches is spread out instead of hammering the sites.
MIN_INTERVAL = float(os.environ.get("FURIMA_MIN_INTERVAL", "1.0"))  # seconds between requests
MAX_RETRIES = 2  # on 429 / 503, honouring Retry-After
MAX_RETRY_WAIT = 30.0  # never sleep longer than this for one retry

_last_request: dict[str, float] = {}
_host_locks: dict[tuple[int, str], asyncio.Lock] = {}


async def _wait_turn(host: str) -> None:
    """Block until `host` has had no request for MIN_INTERVAL seconds."""
    key = (id(asyncio.get_running_loop()), host)
    lock = _host_locks.setdefault(key, asyncio.Lock())
    async with lock:
        delay = _last_request.get(host, 0.0) + MIN_INTERVAL - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)
        _last_request[host] = time.monotonic()


def retry_after(response: httpx.Response, attempt: int) -> float:
    """Seconds to wait before retrying: the server's Retry-After, else exponential backoff."""
    value = response.headers.get("Retry-After", "").strip()
    wait = 2.0 * 2**attempt
    if value.isdigit():
        wait = float(value)
    elif value:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed is not None:
            wait = parsed.timestamp() - time.time()
    return min(max(wait, 0.0), MAX_RETRY_WAIT)


class PoliteTransport(httpx.AsyncBaseTransport):
    """Rate-limits each host and retries 429 / 503 a couple of times."""

    def __init__(self) -> None:
        self._inner = httpx.AsyncHTTPTransport(retries=1)  # connect-level retries only

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        for attempt in range(MAX_RETRIES + 1):
            await _wait_turn(request.url.host)
            response = await self._inner.handle_async_request(request)
            if response.status_code not in (429, 503) or attempt == MAX_RETRIES:
                return response
            wait = retry_after(response, attempt)
            await response.aclose()
            await asyncio.sleep(wait)
        raise AssertionError("unreachable")

    async def aclose(self) -> None:
        await self._inner.aclose()


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=PoliteTransport(),
        timeout=TIMEOUT,
        follow_redirects=True,
        max_redirects=5,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "ja,en;q=0.8"},
    )


async def get_html(client: httpx.AsyncClient, url: str) -> str:
    r = await client.get(url)
    # Yahoo Auctions answers "no results" with a 404 that still carries a normal page.
    if r.status_code >= 500 or r.status_code in (403, 429):
        r.raise_for_status()
    return r.text


def next_data(html: str) -> dict | None:
    """The Next.js page payload, or None when the page has none."""
    m = _NEXT_DATA.search(html or "")
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def dig(data, *path):
    """data[path[0]][path[1]]..., or None as soon as a step is missing."""
    for key in path:
        if isinstance(data, dict):
            data = data.get(key)
        elif isinstance(data, list) and isinstance(key, int) and -len(data) <= key < len(data):
            data = data[key]
        else:
            return None
    return data


def to_int(value) -> int | None:
    try:
        return int(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


JST = dt.timezone(dt.timedelta(hours=9))


def unix_to_iso(ts) -> str | None:
    """Unix seconds (int or numeric string) -> ISO 8601 in Japan time."""
    n = to_int(ts)
    if n is None or n <= 0:
        return None
    return dt.datetime.fromtimestamp(n, JST).isoformat()
