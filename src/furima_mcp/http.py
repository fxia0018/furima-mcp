"""Shared HTTP helpers."""

from __future__ import annotations

import datetime as dt
import json
import re

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
TIMEOUT = httpx.Timeout(20.0, connect=10.0)

_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=TIMEOUT,
        follow_redirects=True,
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
