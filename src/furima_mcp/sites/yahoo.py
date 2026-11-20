"""Yahoo! Auctions (auctions.yahoo.co.jp).

Both the live search and the closed-auction search (落札相場, the last ~180 days of
final prices) are server-rendered Next.js pages, so the listings are in __NEXT_DATA__.
"""

from __future__ import annotations

import re
from urllib.parse import urlencode

import httpx

from ..http import dig, get_html, next_data, to_int
from ..models import Listing, Query, SiteResult

NAME = "yahoo"
PAGE_SIZE = 100
HOSTS = ("auctions.yahoo.co.jp", "page.auctions.yahoo.co.jp")
PAYPAY_ITEM_URL = "https://paypayfleamarket.yahoo.co.jp/item/"
ITEM_URL_PATTERN = re.compile(r"auctions\.yahoo\.co\.jp/jp/auction/([A-Za-z0-9]+)")

_SORT = {
    "relevance": {},
    "newest": {"s1": "new", "o1": "d"},
    "price_asc": {"s1": "cbids", "o1": "a"},
    "price_desc": {"s1": "cbids", "o1": "d"},
}
# Yahoo! Auctions and Yahoo! Flea Market share these codes (Flea Market in lower case).
CONDITION_OF = {
    "NEW": "new",
    "USED10": "like_new",
    "USED20": "good",
    "USED40": "fair",
    "USED60": "poor",
    "USED80": "bad",
}


def search_url(q: Query, offset: int = 1) -> str:
    path = "closedsearch/closedsearch" if q.sold else "search/search"
    params: dict = {"p": q.keyword, "n": PAGE_SIZE, "b": offset}
    # Closed search is newest-ended first by default, which is what price history wants.
    if not (q.sold and q.sort == "relevance"):
        params.update(_SORT[q.sort])
    if q.min_price:
        params["aucminprice"] = q.min_price
    if q.max_price:
        params["aucmaxprice"] = q.max_price
    # The search only filters new vs used; finer conditions are filtered on our side.
    if q.conditions and set(q.conditions) == {"new"}:
        params["istatus"] = 1
    elif q.conditions and "new" not in q.conditions:
        params["istatus"] = 2
    return f"https://auctions.yahoo.co.jp/{path}?{urlencode(params)}"


def parse_search(html: str, sold: bool) -> tuple[list[Listing], int | None]:
    block = dig(next_data(html), "props", "pageProps", "initialState", "search", "items", "listing")
    if not isinstance(block, dict):
        return [], None
    out = []
    for it in block.get("items") or []:
        aid = it.get("auctionId")
        if not aid:
            continue
        common = {
            "id": aid,
            "title": (it.get("title") or "").strip(),
            "price": to_int(it.get("price")),
            "image": it.get("imageUrl"),
            "condition": CONDITION_OF.get(it.get("itemCondition") or ""),
            "sold": sold,
            "listed_at": it.get("startTime"),
            "sold_at": it.get("endTime") if sold else None,
        }
        if it.get("isFleamarketItem"):
            # Yahoo! Flea Market items show up here too, under the same id. Label them as
            # paypay so they are not counted twice next to the paypay search.
            out.append(Listing(site="paypay", url=f"{PAYPAY_ITEM_URL}{aid}", **common))
            continue
        fixed = bool(it.get("isFixedPrice"))  # a buy-now price, not a bid
        out.append(
            Listing(
                site=NAME,
                url=f"https://auctions.yahoo.co.jp/jp/auction/{aid}",
                is_auction=not sold and not fixed and bool(it.get("endTime")),
                bids=to_int(it.get("bidCount")) if not fixed else None,
                ends_at=None if sold else it.get("endTime"),
                **common,
            )
        )
    return out, to_int(block.get("totalResultsAvailable"))


async def search(client: httpx.AsyncClient, q: Query) -> SiteResult:
    res = SiteResult(site=NAME)
    offset = 1
    while len(res.listings) < q.limit:
        html = await get_html(client, search_url(q, offset))
        listings, total = parse_search(html, q.sold)
        res.listings += listings
        res.total = total
        offset += PAGE_SIZE
        if len(listings) < PAGE_SIZE or (total is not None and offset > total):
            break
    res.listings = res.listings[: q.limit]
    return res


def parse_item(html: str) -> dict | None:
    it = dig(next_data(html), "props", "pageProps", "initialState", "item", "detail", "item")
    if not isinstance(it, dict):
        return None
    seller = it.get("seller") or {}
    desc = it.get("description")
    images = [i.get("image") for i in it.get("img") or [] if isinstance(i, dict) and i.get("image")]
    return {
        "site": NAME,
        "id": it.get("auctionId"),
        "title": it.get("title"),
        "price": to_int(it.get("price")),
        "buy_now_price": to_int(it.get("bidorbuy")),
        "status": "open" if it.get("status") == "open" else "closed",
        "bids": to_int(it.get("bids")),
        "ends_at": it.get("endTime"),
        "auto_extension": bool(it.get("isAutomaticExtension")),
        "condition": it.get("conditionName"),
        "description": "\n".join(desc) if isinstance(desc, list) else desc,
        "images": images,
        "seller": {
            "id": seller.get("aucUserId"),
            "good_rating": dig(seller, "rating", "goodRating"),
            "ratings": dig(seller, "rating", "summary"),
            "is_store": bool(seller.get("isStore")),
        },
        "url": f"https://auctions.yahoo.co.jp/jp/auction/{it.get('auctionId')}",
    }


async def item(client: httpx.AsyncClient, url: str) -> dict | None:
    m = ITEM_URL_PATTERN.search(url)
    if not m:
        return None
    html = await get_html(client, f"https://auctions.yahoo.co.jp/jp/auction/{m.group(1)}")
    return parse_item(html)
