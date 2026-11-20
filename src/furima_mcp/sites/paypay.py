"""Yahoo! Flea Market (paypayfleamarket.yahoo.co.jp), formerly PayPay Flea Market.

Fixed-price C2C, like Mercari. Search results are in __NEXT_DATA__. The site has no
searchable sold history of its own; sold Flea Market items come back through the Yahoo!
Auctions closed search instead (see yahoo.py).
"""

from __future__ import annotations

import re
from urllib.parse import quote, urlencode

import httpx

from ..http import dig, get_html, next_data, to_int
from ..models import Listing, Query, SiteResult
from .yahoo import CONDITION_OF

NAME = "paypay"
PAGE_SIZE = 100
HOSTS = ("paypayfleamarket.yahoo.co.jp",)
ITEM_URL_PATTERN = re.compile(r"paypayfleamarket\.yahoo\.co\.jp/item/([A-Za-z0-9]+)")

_CODE = {v: k for k, v in CONDITION_OF.items()}
_SORT = {
    "relevance": {},
    "newest": {"sort": "openTime", "order": "desc"},
    "price_asc": {"sort": "price", "order": "asc"},
    "price_desc": {"sort": "price", "order": "desc"},
}


def search_url(q: Query, page: int = 1) -> str:
    params: dict = {"open": 1, **_SORT[q.sort]}  # open=1: on sale only
    if q.min_price:
        params["minPrice"] = q.min_price
    if q.max_price:
        params["maxPrice"] = q.max_price
    if q.conditions:
        params["conditions"] = ",".join(_CODE[c] for c in q.conditions)
    if page > 1:
        params["page"] = page
    return f"https://paypayfleamarket.yahoo.co.jp/search/{quote(q.keyword, safe='')}?{urlencode(params)}"


def parse_search(html: str) -> tuple[list[Listing], int | None]:
    result = dig(next_data(html), "props", "initialState", "searchState", "search", "result")
    if not isinstance(result, dict):
        return [], None
    out = []
    for it in result.get("items") or []:
        iid = it.get("id")
        if not iid:
            continue
        out.append(
            Listing(
                site=NAME,
                id=iid,
                title=(it.get("title") or "").strip(),
                price=to_int(it.get("price")),
                url=f"https://paypayfleamarket.yahoo.co.jp/item/{iid}",
                image=it.get("thumbnailImageUrl"),
                condition=CONDITION_OF.get(str(it.get("condition") or "").upper()),
                listed_at=it.get("openTime"),
            )
        )
    return out, to_int(result.get("totalResultsAvailable"))


async def search(client: httpx.AsyncClient, q: Query) -> SiteResult:
    res = SiteResult(site=NAME)
    if q.sold:
        return res
    page = 1
    while len(res.listings) < q.limit:
        listings, total = parse_search(await get_html(client, search_url(q, page)))
        res.listings += listings
        res.total = total
        if len(listings) < PAGE_SIZE or (total is not None and page * PAGE_SIZE >= total):
            break
        page += 1
    res.listings = res.listings[: q.limit]
    return res


def parse_item(html: str) -> dict | None:
    it = dig(next_data(html), "props", "initialState", "itemsState", "items", "item")
    if not isinstance(it, dict):
        return None
    seller = it.get("seller") or {}
    return {
        "site": NAME,
        "id": it.get("id"),
        "title": it.get("title"),
        "price": to_int(it.get("price")),
        "status": "on_sale" if it.get("status") == "OPEN" else "sold",
        "condition": dig(it, "condition", "text"),
        "description": it.get("description"),
        "images": [i.get("url") for i in it.get("images") or [] if isinstance(i, dict) and i.get("url")],
        "likes": it.get("likeCount"),
        "listed_at": it.get("openDate") or it.get("createDate"),
        "seller": {
            "id": seller.get("id"),
            "name": seller.get("nickname"),
            "ratings": dig(seller, "rating", "total"),
            "good_ratio": dig(seller, "rating", "goodRatio"),
        },
        "url": f"https://paypayfleamarket.yahoo.co.jp/item/{it.get('id')}",
    }


async def item(client: httpx.AsyncClient, url: str) -> dict | None:
    m = ITEM_URL_PATTERN.search(url)
    if not m:
        return None
    html = await get_html(client, f"https://paypayfleamarket.yahoo.co.jp/item/{m.group(1)}")
    return parse_item(html)
