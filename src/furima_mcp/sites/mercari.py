"""Mercari Japan (jp.mercari.com).

The web app is a client-rendered SPA, so the HTML has no listings. It reads them from
api.mercari.jp, which only asks for a DPoP proof: a short JWT signed with any P-256 key
the client makes up. No account or cookie is involved.
"""

from __future__ import annotations

import base64
import json
import re
import time
import uuid

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from ..http import dig, to_int, unix_to_iso
from ..models import Listing, Query, SiteResult

NAME = "mercari"
SEARCH_URL = "https://api.mercari.jp/v2/entities:search"
ITEM_URL = "https://api.mercari.jp/items/get"
HOSTS = ("jp.mercari.com", "mercari.com", "www.mercari.com")
ITEM_URL_PATTERN = re.compile(r"mercari\.com/(?:[a-z]{2}/)?(item|shops/product)/([A-Za-z0-9]+)")
PAGE_SIZE = 120

_SORT = {
    "relevance": ("SORT_SCORE", "ORDER_DESC"),
    "newest": ("SORT_CREATED_TIME", "ORDER_DESC"),
    "price_asc": ("SORT_PRICE", "ORDER_ASC"),
    "price_desc": ("SORT_PRICE", "ORDER_DESC"),
}


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class _DPoP:
    """Signs DPoP proofs with one key per process."""

    def __init__(self) -> None:
        self._key = ec.generate_private_key(ec.SECP256R1())
        pub = self._key.public_key().public_numbers()
        self._jwk = {
            "crv": "P-256",
            "kty": "EC",
            "x": _b64(pub.x.to_bytes(32, "big")),
            "y": _b64(pub.y.to_bytes(32, "big")),
        }

    def proof(self, method: str, url: str) -> str:
        header = {"typ": "dpop+jwt", "alg": "ES256", "jwk": self._jwk}
        payload = {
            "iat": int(time.time()),
            "jti": str(uuid.uuid4()),
            "htu": url,
            "htm": method,
            "uuid": str(uuid.uuid4()),
        }
        signing_input = ".".join(
            _b64(json.dumps(part, separators=(",", ":")).encode()) for part in (header, payload)
        )
        der = self._key.sign(signing_input.encode(), ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der)
        return f"{signing_input}.{_b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


_dpop: _DPoP | None = None


def _headers(method: str, url: str) -> dict:
    global _dpop
    if _dpop is None:
        _dpop = _DPoP()
    return {"DPoP": _dpop.proof(method, url), "X-Platform": "web", "Accept": "application/json"}


def search_body(q: Query, page_token: str = "") -> dict:
    sort, order = _SORT[q.sort]
    cond: dict = {
        "keyword": q.keyword,
        "sort": sort,
        "order": order,
        "status": ["STATUS_SOLD_OUT", "STATUS_TRADING"] if q.sold else ["STATUS_ON_SALE"],
    }
    if q.min_price:
        cond["priceMin"] = q.min_price
    if q.max_price:
        cond["priceMax"] = q.max_price
    return {
        "pageSize": PAGE_SIZE,
        "pageToken": page_token,
        "searchSessionId": uuid.uuid4().hex,
        "searchCondition": cond,
        "defaultDatasets": ["DATASET_TYPE_MERCARI", "DATASET_TYPE_BEYOND"],
        "serviceFrom": "suruga",
        "withItemBrand": True,
        "withItemSize": False,
        "withItemPromotions": False,
        "withItemSizes": False,
        "withShopname": False,
    }


def parse_search(data: dict) -> list[Listing]:
    out = []
    for it in data.get("items") or []:
        iid = it.get("id")
        if not iid:
            continue
        shop = it.get("itemType") == "ITEM_TYPE_BEYOND"
        path = f"shops/product/{iid}" if shop else f"item/{iid}"
        sold = it.get("status") not in (None, "ITEM_STATUS_ON_SALE")
        auction = it.get("auction") or None
        thumbs = it.get("thumbnails") or []
        out.append(
            Listing(
                site=NAME,
                id=iid,
                title=(it.get("name") or "").strip(),
                price=to_int(it.get("price")),
                url=f"https://jp.mercari.com/{path}",
                image=thumbs[0] if thumbs else None,
                sold=sold,
                is_auction=bool(auction) and not sold,
                bids=to_int(auction.get("totalBid")) if auction else None,
                ends_at=auction.get("bidDeadline") if auction else None,
                listed_at=unix_to_iso(it.get("created")),
                sold_at=unix_to_iso(it.get("updated")) if sold else None,
            )
        )
    return out


async def search(client: httpx.AsyncClient, q: Query) -> SiteResult:
    res = SiteResult(site=NAME)
    token = ""
    while len(res.listings) < q.limit:
        r = await client.post(
            SEARCH_URL,
            json=search_body(q, token),
            headers=_headers("POST", SEARCH_URL),
        )
        r.raise_for_status()
        data = r.json()
        res.listings += parse_search(data)
        res.total = to_int(dig(data, "meta", "numFound"))
        token = dig(data, "meta", "nextPageToken") or ""
        if not token or not data.get("items"):
            break
    res.listings = res.listings[: q.limit]
    return res


def parse_item(data: dict) -> dict:
    d = data.get("data") or {}
    seller = d.get("seller") or {}
    ratings = seller.get("ratings") or {}
    return {
        "site": NAME,
        "id": d.get("id"),
        "title": d.get("name"),
        "price": to_int(d.get("price")),
        "status": "on_sale" if d.get("status") == "on_sale" else "sold",
        "condition": dig(d, "item_condition", "name"),
        "shipping_paid_by": dig(d, "shipping_payer", "code"),
        "description": d.get("description"),
        "images": d.get("photos") or [],
        "likes": d.get("num_likes"),
        "listed_at": unix_to_iso(d.get("created")),
        "updated_at": unix_to_iso(d.get("updated")),
        "seller": {
            "id": str(seller.get("id")) if seller.get("id") else None,
            "name": seller.get("name"),
            "ratings_good": ratings.get("good"),
            "ratings_bad": ratings.get("bad"),
        },
        "url": f"https://jp.mercari.com/item/{d.get('id')}",
    }


async def item(client: httpx.AsyncClient, url: str) -> dict | None:
    m = ITEM_URL_PATTERN.search(url)
    if not m:
        return None
    if m.group(1) != "item":
        raise ValueError("Mercari Shops products are not supported yet")
    r = await client.get(
        ITEM_URL,
        params={"id": m.group(2), "include_item_attributes": "true"},
        headers=_headers("GET", ITEM_URL),
    )
    if r.status_code == 404:
        raise ValueError("listing not found (deleted or never existed)")
    r.raise_for_status()
    return parse_item(r.json())
