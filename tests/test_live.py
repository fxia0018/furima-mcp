"""Checks against the real sites. Skipped by default; run with `pytest -m live`.

The scheduled live-check workflow runs these daily, so a site layout change shows up as
a failing test (and an issue) before users notice.
"""

import pytest

from furima_mcp import http, server
from furima_mcp.http import new_client
from furima_mcp.models import Query
from furima_mcp.sites import SITES, SOLD_SITES

pytestmark = pytest.mark.live

KEYWORD = "ピカチュウ ぬいぐるみ"


@pytest.fixture(autouse=True)
def _polite(monkeypatch):
    # conftest turns the delay off for offline tests; keep it on for real sites.
    monkeypatch.setattr(http, "MIN_INTERVAL", 1.0)


def _check_listings(listings, site):
    assert listings, f"{site}: no listings parsed"
    for l in listings:
        assert l.title and l.url.startswith("https://"), l
        assert isinstance(l.price, int) and l.price > 0, l


@pytest.mark.parametrize("site", list(SITES))
async def test_search_for_sale(site):
    async with new_client() as client:
        res = await SITES[site].search(client, Query(KEYWORD, limit=10))
    _check_listings(res.listings, site)
    assert not any(l.sold for l in res.listings if l.site == site)
    if site != "rakuma":  # Rakuma cards carry no condition unless filtered
        assert any(l.condition for l in res.listings), f"{site}: no conditions parsed"


@pytest.mark.parametrize("site", SOLD_SITES)
async def test_search_sold(site):
    async with new_client() as client:
        res = await SITES[site].search(client, Query(KEYWORD, sold=True, limit=10))
    _check_listings(res.listings, site)
    assert all(l.sold for l in res.listings), f"{site}: sold search returned unsold listings"


@pytest.mark.parametrize("site", list(SITES))
async def test_listing_details(site):
    async with new_client() as client:
        res = await SITES[site].search(client, Query(KEYWORD, limit=5))
        first = next(l for l in res.listings if l.site == site and "/shops/" not in l.url)
        detail = await SITES[site].item(client, first.url)
    assert detail and detail["title"] and isinstance(detail["price"], int), detail


async def test_condition_filter():
    async with new_client() as client:
        res = await SITES["mercari"].search(client, Query(KEYWORD, conditions=("new",), limit=10))
    assert res.listings and all(l.condition == "new" for l in res.listings)


async def test_tools_end_to_end():
    out = await server.search_listings(KEYWORD, limit_per_site=5)
    assert out["errors"] == {}, out["errors"]
    assert {l["site"] for l in out["listings"]} == set(SITES)
    stats = await server.sold_price_stats(KEYWORD, sample=30, match_all_words=False)
    assert stats["errors"] == {} and stats["overall"]["count"] > 0
