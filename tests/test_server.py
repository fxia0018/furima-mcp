"""End-to-end tool calls with every site mocked."""

import httpx
import pytest
import respx

from furima_mcp import http, server

from . import fixtures as fx


@pytest.fixture
def sites():
    with respx.mock(assert_all_called=False) as mock:
        mock.post("https://api.mercari.jp/v2/entities:search").respond(json=fx.MERCARI_SEARCH)
        mock.get("https://api.mercari.jp/items/get").respond(json=fx.MERCARI_ITEM)
        mock.get(url__regex=r"https://auctions\.yahoo\.co\.jp/search/").respond(
            text=fx.yahoo_search(fx.YAHOO_LIVE_ITEMS, 2)
        )
        mock.get(url__regex=r"https://auctions\.yahoo\.co\.jp/closedsearch/").respond(
            text=fx.yahoo_search(fx.YAHOO_CLOSED_ITEMS, 2, "/closedsearch")
        )
        mock.get(url__regex=r"https://paypayfleamarket\.yahoo\.co\.jp/search/").respond(
            text=fx.paypay_search(fx.PAYPAY_ITEMS, 1)
        )
        mock.get(url__regex=r"https://fril\.jp/s\?").respond(text=fx.RAKUMA_SEARCH)
        mock.get("https://item.fril.jp/aaa111").respond(text=fx.RAKUMA_ITEM)
        yield mock


async def test_search_listings_merges_all_sites(sites):
    out = await server.search_listings("テスト", sort="price_asc")
    prices = [l["price"] for l in out["listings"]]
    assert prices == sorted(prices)
    assert {l["site"] for l in out["listings"]} == {"mercari", "yahoo", "paypay", "rakuma"}
    assert out["errors"] == {}
    assert out["total_matches"]["mercari"] == 2


async def test_one_failing_site_is_reported_not_raised(sites, monkeypatch):
    monkeypatch.setattr(http, "MAX_RETRIES", 0)
    sites.get(url__regex=r"https://fril\.jp/s\?").respond(status_code=503)
    out = await server.search_listings("テスト", sites=["rakuma", "paypay"])
    assert out["errors"] == {"rakuma": "HTTP 503"}
    assert [l["site"] for l in out["listings"]] == ["paypay"]


async def test_sold_price_stats_and_check_price(sites):
    out = await server.sold_price_stats("テスト", match_all_words=False)
    # sold only: the mercari Shops item, both Yahoo closed auctions, the sold Rakuma card
    assert sorted(l["price"] for l in out["recent_sales"]) == [800, 3000, 4000, 5000]
    assert set(out["by_site"]) == {"mercari", "yahoo", "rakuma"}

    out = await server.check_price("テスト", 1000, match_all_words=False)
    assert out["percentile"] == 25.0
    assert out["verdict"] == "not enough sold data to judge"


async def test_get_listing_routes_by_url(sites):
    d = await server.get_listing("https://item.fril.jp/aaa111")
    assert d["site"] == "rakuma" and d["status"] == "sold"
    d = await server.get_listing("https://jp.mercari.com/item/m111")
    assert d["site"] == "mercari" and d["price"] == 3000
    with pytest.raises(ValueError, match="not a supported listing URL"):
        await server.get_listing("https://example.com/item/1")


async def test_tools_are_registered_read_only():
    tools = await server.mcp.list_tools()
    names = {t.name for t in tools}
    assert names == {"search_listings", "new_listings", "sold_price_stats", "check_price", "get_listing"}
    assert all(t.annotations.read_only_hint for t in tools)
    search = next(t for t in tools if t.name == "search_listings")
    assert "price_asc" in str(search.input_schema)


@pytest.mark.live
async def test_live_smoke():
    out = await server.search_listings("ピカチュウ ぬいぐるみ", limit_per_site=5)
    assert out["errors"] == {}, out["errors"]
    assert {l["site"] for l in out["listings"]} == {"mercari", "yahoo", "paypay", "rakuma"}
    assert all(isinstance(l["price"], int) for l in out["listings"])


def test_http_client_follows_redirects():
    from furima_mcp.http import new_client

    assert new_client().follow_redirects is True
    assert isinstance(new_client(), httpx.AsyncClient)


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        server.main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"furima-mcp {server.__version__}"


def test_help_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        server.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "claude mcp add furima -- uvx furima-mcp" in out


async def test_new_listings_starts_then_reports_nothing_new(sites):
    first = await server.new_listings("テスト", match_all_words=False)
    assert first["started"] is True and first["count"] > 0
    # Timed listings come first, newest first; Rakuma (no listing time) after them.
    times = [l["listed_at"] for l in first["listings"] if "listed_at" in l]
    assert times == sorted(times, reverse=True)
    again = await server.new_listings("テスト", cursor=first["cursor"], match_all_words=False)
    assert again["started"] is False
    assert again["count"] == 0 and again["may_have_missed"] == []


async def test_new_listings_rejects_a_cursor_from_another_query(sites):
    first = await server.new_listings("テスト")
    with pytest.raises(ValueError, match="different query"):
        await server.new_listings("べつ", cursor=first["cursor"])


async def test_sold_stats_break_down_by_condition(sites):
    out = await server.sold_price_stats("落札品", sites=["yahoo"], match_all_words=False)
    assert out["by_condition"] == {
        "new": {"count": 1, "min": 3000, "max": 3000, "p25": 3000, "median": 3000, "p75": 3000, "mean": 3000},
        "fair": {
            "count": 1,
            "min": 4000,
            "max": 4000,
            "p25": 4000,
            "median": 4000,
            "p75": 4000,
            "mean": 4000,
        },
    }
    only_new = await server.check_price(
        "落札品", 3500, sites=["yahoo"], conditions=["new"], match_all_words=False
    )
    assert only_new["sold_stats"]["count"] == 1
