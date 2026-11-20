"""Rakuma (fril.jp), Rakuten's flea market.

Server-rendered HTML. Every search card carries its data as attributes on the link:
  <a href="https://item.fril.jp/<hash>" class="link_search_image"
     data-rat-itemid="<seller>/<item>" data-rat-item_name="..." data-rat-price="4300"
     data-rat-cp-search_sales_status="販売中|売り切れ" data-rat-cp-totalresults="104450">
    <img data-original="https://img.fril.jp/img/...jpg">
"""

from __future__ import annotations

import html as htmllib
import json
import re
from itertools import chain, zip_longest
from urllib.parse import urlencode

import httpx

from ..http import get_html, to_int
from ..models import Listing, Query, SiteResult

NAME = "rakuma"
PAGE_SIZE = 40
HOSTS = ("item.fril.jp",)
ITEM_URL_PATTERN = re.compile(r"item\.fril\.jp/([a-z0-9]+)")

_SORT = {
    "relevance": ("relevance", "desc"),
    "newest": ("created_at", "desc"),
    "price_asc": ("sell_price", "asc"),
    "price_desc": ("sell_price", "desc"),
}
# Search filter values; the result cards themselves don't show the condition.
_STATUS = {"new": 5, "like_new": 4, "good": 6, "fair": 3, "poor": 2, "bad": 1}
_CARD = re.compile(r'<a\s[^>]*class="link_search_image"[^>]*>.*?</a>', re.S)
_TOTAL = re.compile(r'data-rat-cp-totalresults="(\d+)"')


def search_url(q: Query, page: int = 1, condition: str | None = None) -> str:
    sort, order = _SORT["newest" if q.sold and q.sort == "relevance" else q.sort]
    params: dict = {
        "query": q.keyword,
        "transaction": "soldout" if q.sold else "selling",
        "sort": sort,
        "order": order,
    }
    if q.min_price:
        params["min"] = q.min_price
    if q.max_price:
        params["max"] = q.max_price
    if condition:
        params["status"] = _STATUS[condition]
    if page > 1:
        params["page"] = page
    return f"https://fril.jp/s?{urlencode(params)}"


def _attr(tag: str, name: str) -> str | None:
    m = re.search(rf'\s{re.escape(name)}="([^"]*)"', tag)
    return htmllib.unescape(m.group(1)) if m else None


def parse_search(html: str) -> tuple[list[Listing], int | None]:
    out, seen = [], set()
    for card in _CARD.findall(html or ""):
        href = _attr(card, "href")
        iid = href.rstrip("/").rsplit("/", 1)[-1] if href else None
        if not href or not iid or iid in seen:
            continue
        seen.add(iid)
        numeric = (_attr(card, "data-rat-itemid") or "").rpartition("/")[2]
        out.append(
            Listing(
                site=NAME,
                id=iid,
                title=(_attr(card, "data-rat-item_name") or "").strip(),
                price=to_int(_attr(card, "data-rat-price")),
                url=href,
                image=_attr(card, "data-original"),
                sold=_attr(card, "data-rat-cp-search_sales_status") == "売り切れ",
                seq=int(numeric) if numeric.isdigit() else None,
            )
        )
    m = _TOTAL.search(html or "")
    return out, int(m.group(1)) if m else None


async def _search(client: httpx.AsyncClient, q: Query, condition: str | None) -> SiteResult:
    res = SiteResult(site=NAME)
    page = 1
    while len(res.listings) < q.limit:
        listings, total = parse_search(await get_html(client, search_url(q, page, condition)))
        for listing in listings:
            listing.condition = condition
        res.listings += listings
        res.total = total
        if len(listings) < PAGE_SIZE or (total is not None and page * PAGE_SIZE >= total):
            break
        page += 1
    res.listings = res.listings[: q.limit]
    return res


async def search(client: httpx.AsyncClient, q: Query) -> SiteResult:
    if not q.conditions:
        return await _search(client, q, None)
    # One search per condition, so every listing knows its condition.
    parts = [await _search(client, q, c) for c in q.conditions]
    if q.sort in ("price_asc", "price_desc"):
        listings = sorted(chain(*(p.listings for p in parts)), key=lambda l: l.price or 0)
        if q.sort == "price_desc":
            listings.reverse()
    else:
        listings = [l for row in zip_longest(*(p.listings for p in parts)) for l in row if l]
    total = sum(p.total or 0 for p in parts) if all(p.total is not None for p in parts) else None
    return SiteResult(site=NAME, listings=listings[: q.limit], total=total)


def parse_item(html: str, url: str) -> dict | None:
    product = None
    for m in re.finditer(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", html or "", re.S):
        try:
            node = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(node, dict) and node.get("@type") == "Product":
            product = node
            break
    if product is None:
        return None
    offers = product.get("offers") or {}
    cond = re.search(r"item-status-status[^<]*</i>[^<]*</th>\s*<td>([^<]+)</td>", html)
    image = product.get("image")
    # The JSON-LD keeps saying InStock after a sale; the page's SOLD OUT badge is what changes.
    return {
        "site": NAME,
        "id": ITEM_URL_PATTERN.search(url).group(1),
        "title": product.get("name"),
        "price": to_int(offers.get("price")),
        "status": "sold" if "SOLD OUT" in html else "on_sale",
        "condition": cond.group(1).strip() if cond else None,
        "description": product.get("description"),
        "images": [image] if isinstance(image, str) else list(image or []),
        "seller": {"name": (offers.get("seller") or {}).get("name")},
        "url": url,
    }


async def item(client: httpx.AsyncClient, url: str) -> dict | None:
    m = ITEM_URL_PATTERN.search(url)
    if not m:
        return None
    canonical = f"https://item.fril.jp/{m.group(1)}"
    return parse_item(await get_html(client, canonical), canonical)
