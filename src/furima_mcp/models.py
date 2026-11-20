"""The normalized shapes every site adapter returns."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

Sort = Literal["relevance", "newest", "price_asc", "price_desc"]

# The six-step condition scale all four marketplaces share, best to worst.
Condition = Literal["new", "like_new", "good", "fair", "poor", "bad"]
CONDITIONS: dict[str, str] = {
    "new": "新品、未使用",
    "like_new": "未使用に近い",
    "good": "目立った傷や汚れなし",
    "fair": "やや傷や汚れあり",
    "poor": "傷や汚れあり",
    "bad": "全体的に状態が悪い",
}


@dataclass
class Query:
    keyword: str
    sold: bool = False
    min_price: int | None = None
    max_price: int | None = None
    sort: Sort = "relevance"
    limit: int = 30
    conditions: tuple[Condition, ...] = ()  # empty: any condition


@dataclass
class Listing:
    site: str
    id: str
    title: str
    price: int | None  # JPY
    url: str
    image: str | None = None
    condition: Condition | None = None  # None: the site's search results don't say
    sold: bool = False
    is_auction: bool = False  # True: price is the current bid and may still rise
    bids: int | None = None
    ends_at: str | None = None  # ISO 8601, auctions only
    listed_at: str | None = None  # ISO 8601
    sold_at: str | None = None  # ISO 8601, sold listings only (Mercari: last update time)
    # Rakuma shows no listing time, but its numeric item ids only grow; used to spot new ones.
    seq: int | None = field(default=None, repr=False)

    def to_dict(self) -> dict:
        d = asdict(self)
        del d["seq"]
        return {k: v for k, v in d.items() if v not in (None, False)}


@dataclass
class SiteResult:
    site: str
    listings: list[Listing] = field(default_factory=list)
    total: int | None = None  # matches the site reports, when it says
    error: str | None = None
