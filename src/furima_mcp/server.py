"""MCP server: search Japanese second-hand marketplaces and their sold prices."""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from . import __version__
from .core import errors_of, merge, percentile_of, pick_sites, price_stats, search_sites, verdict
from .http import new_client
from .models import Query
from .sites import SITES

SiteName = Literal["mercari", "yahoo", "paypay", "rakuma"]

INSTRUCTIONS = """\
Search Japanese second-hand marketplaces: Mercari (mercari), Yahoo! Auctions (yahoo),
Yahoo! Flea Market / PayPay Flea Market (paypay) and Rakuma (rakuma). Prices are in JPY.

Tips:
- Search in Japanese. Product names, series names and model numbers work best
  (e.g. "ポケモンカード ピカチュウ 25th", "PS5 CFI-2000", "ドラクエ3 SFC 箱説").
- Results are keyword matches and include accessories, bundles and junk. Use `exclude`
  (e.g. ["ジャンク", "空箱", "ケースのみ"]) and price bounds to keep the comparison fair.
- Yahoo auction prices with is_auction=true are current bids and may still rise.
- Use sold_price_stats or check_price before calling something a good deal.
"""

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)

mcp = MCPServer("furima", instructions=INSTRUCTIONS, version=__version__)

Keyword = Annotated[str, Field(description="Search keyword, ideally in Japanese.", min_length=1)]
Sites = Annotated[
    list[SiteName] | None,
    Field(description="Sites to search. Default: all that support the operation."),
]
MinPrice = Annotated[int | None, Field(description="Minimum price in JPY.", ge=0)]
MaxPrice = Annotated[int | None, Field(description="Maximum price in JPY.", ge=0)]
MatchAll = Annotated[
    bool,
    Field(
        description="Keep only listings whose title contains every word of the query "
        "(ignoring width, case, spaces and hyphens). The sites' own search is fuzzy: "
        "'PS5 CFI-2000' also returns PS5 games."
    ),
]
Exclude = Annotated[
    list[str] | None,
    Field(description="Drop listings whose title contains any of these words (case-insensitive)."),
]


@mcp.tool(annotations=READ_ONLY)
async def search_listings(
    query: Keyword,
    sites: Sites = None,
    min_price: MinPrice = None,
    max_price: MaxPrice = None,
    sort: Annotated[
        Literal["relevance", "newest", "price_asc", "price_desc"],
        Field(description="Order of results. price_* sorts across all sites."),
    ] = "relevance",
    limit_per_site: Annotated[int, Field(ge=1, le=300)] = 20,
    exclude: Exclude = None,
    match_all_words: MatchAll = False,
) -> dict:
    """Search listings that are for sale now on Japanese marketplaces.

    Returns the merged listings (site, title, price in JPY, url, image, and for auctions
    the current bid count and end time), the total matches each site reports, and any
    site that failed.
    """
    q = Query(query, False, min_price, max_price, sort, limit_per_site)
    async with new_client() as client:
        results = await search_sites(client, pick_sites(sites, sold=False), q)
    listings = merge(results, q, exclude, match_all_words)
    return {
        "query": query,
        "count": len(listings),
        "total_matches": {r.site: r.total for r in results if r.total is not None},
        "listings": [l.to_dict() for l in listings],
        "errors": errors_of(results),
    }


async def _sold(query, sites, min_price, max_price, sample, exclude, match_all):
    # "relevance" on a sold search: Mercari ranks by match quality (its newest-first view is
    # mostly loose matches), Yahoo and Rakuma return the most recent sales.
    q = Query(query, True, min_price, max_price, "relevance", sample)
    async with new_client() as client:
        results = await search_sites(client, pick_sites(sites, sold=True), q)
    listings = merge(results, q, exclude, match_all)
    return results, listings


SoldSites = Annotated[
    list[Literal["mercari", "yahoo", "rakuma"]] | None,
    Field(description="Sites with sold history to use. Default: mercari, yahoo, rakuma."),
]
Sample = Annotated[
    int,
    Field(description="Sold listings to read per site before filtering.", ge=10, le=300),
]


@mcp.tool(annotations=READ_ONLY)
async def sold_price_stats(
    query: Keyword,
    sites: SoldSites = None,
    min_price: MinPrice = None,
    max_price: MaxPrice = None,
    sample: Sample = 100,
    exclude: Exclude = None,
    match_all_words: MatchAll = True,
) -> dict:
    """What an item actually sells for: statistics over recently sold listings.

    Reads the most recent sold listings from Mercari, Yahoo! Auctions (final prices) and
    Rakuma, and returns count, min, p25, median, p75, max and mean overall and per site,
    plus a few recent sales as examples.
    """
    results, listings = await _sold(query, sites, min_price, max_price, sample, exclude, match_all_words)
    by_site = {r.site: [l.price for l in listings if l.site == r.site] for r in results}
    return {
        "query": query,
        "overall": price_stats([l.price for l in listings]),
        "by_site": {s: price_stats(p) for s, p in by_site.items() if p},
        "recent_sales": [l.to_dict() for l in listings[:10]],
        "errors": errors_of(results),
    }


@mcp.tool(annotations=READ_ONLY)
async def check_price(
    query: Keyword,
    price: Annotated[int, Field(description="The asking price in JPY to judge.", ge=0)],
    sites: SoldSites = None,
    min_price: MinPrice = None,
    max_price: MaxPrice = None,
    sample: Sample = 100,
    exclude: Exclude = None,
    match_all_words: MatchAll = True,
) -> dict:
    """Judge whether a price is cheap or expensive against recent sold prices.

    Returns the price's percentile among recent sales (0 = cheaper than every sale,
    100 = dearer than every sale), a one-line verdict, and the sold-price statistics.
    """
    results, listings = await _sold(query, sites, min_price, max_price, sample, exclude, match_all_words)
    prices = [l.price for l in listings]
    pct = percentile_of(price, prices)
    return {
        "query": query,
        "price": price,
        "percentile": pct,
        "verdict": verdict(pct, len(prices)),
        "sold_stats": price_stats(prices),
        "errors": errors_of(results),
    }


@mcp.tool(annotations=READ_ONLY)
async def get_listing(
    url: Annotated[
        str, Field(description="A Mercari, Yahoo! Auctions, Yahoo! Flea Market or Rakuma listing URL.")
    ],
) -> dict:
    """Full details of one listing: price, status, condition, description, images and seller."""
    async with new_client() as client:
        for site in SITES.values():
            if site.ITEM_URL_PATTERN.search(url):
                detail = await site.item(client, url)
                if detail is None:
                    raise ValueError("could not read the listing page (layout change or removed)")
                return detail
    raise ValueError(f"not a supported listing URL; supported sites: {', '.join(SITES)}")


def main() -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    mcp.run()


if __name__ == "__main__":
    main()
