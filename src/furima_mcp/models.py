"""The normalized shapes every site adapter returns."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

Sort = Literal["relevance", "newest", "price_asc", "price_desc"]


@dataclass
class Query:
    keyword: str
    sold: bool = False
    min_price: int | None = None
    max_price: int | None = None
    sort: Sort = "relevance"
    limit: int = 30


@dataclass
class Listing:
    site: str
    id: str
    title: str
    price: int | None  # JPY
    url: str
    image: str | None = None
    sold: bool = False
    is_auction: bool = False  # True: price is the current bid and may still rise
    bids: int | None = None
    ends_at: str | None = None  # ISO 8601, auctions only
    listed_at: str | None = None  # ISO 8601
    sold_at: str | None = None  # ISO 8601, sold listings only (Mercari: last update time)

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v not in (None, False)}


@dataclass
class SiteResult:
    site: str
    listings: list[Listing] = field(default_factory=list)
    total: int | None = None  # matches the site reports, when it says
    error: str | None = None
