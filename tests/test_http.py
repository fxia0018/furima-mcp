import time

import httpx
import pytest
import respx

from furima_mcp import core, http, server
from furima_mcp.models import Query


async def test_requests_to_one_host_are_spaced(monkeypatch):
    monkeypatch.setattr(http, "MIN_INTERVAL", 0.2)
    with respx.mock:
        respx.get(url__regex=r"https://a\.example/.*").respond(text="ok")
        respx.get("https://b.example/").respond(text="ok")
        async with http.new_client() as c:
            start = time.monotonic()
            await c.get("https://a.example/1")
            await c.get("https://b.example/")  # another host: no wait
            assert time.monotonic() - start < 0.15
            await c.get("https://a.example/2")
            assert time.monotonic() - start >= 0.2


async def test_429_is_retried_after_retry_after(monkeypatch):
    sleeps = []

    async def fake_sleep(s):
        sleeps.append(s)

    monkeypatch.setattr(http.asyncio, "sleep", fake_sleep)
    with respx.mock:
        route = respx.get("https://a.example/").mock(
            side_effect=[httpx.Response(429, headers={"Retry-After": "3"}), httpx.Response(200, text="ok")]
        )
        async with http.new_client() as c:
            r = await c.get("https://a.example/")
    assert r.text == "ok" and route.call_count == 2 and sleeps == [3.0]


async def test_retries_give_up_and_surface_the_error(monkeypatch):
    async def no_sleep(s):
        pass

    monkeypatch.setattr(http.asyncio, "sleep", no_sleep)
    with respx.mock:
        route = respx.get("https://a.example/").respond(503)
        async with http.new_client() as c:
            with pytest.raises(httpx.HTTPStatusError):
                await http.get_html(c, "https://a.example/")
    assert route.call_count == 1 + http.MAX_RETRIES


def test_retry_after_is_capped():
    resp = httpx.Response(429, headers={"Retry-After": "86400"})
    assert http.retry_after(resp, 0) == http.MAX_RETRY_WAIT
    assert http.retry_after(httpx.Response(503), 1) == 4.0


async def test_successful_results_are_cached_failures_are_not(monkeypatch):
    calls = []

    async def fake_search(client, q):
        calls.append(q)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return core.SiteResult(site="rakuma")

    monkeypatch.setattr(core.SITES["rakuma"], "search", fake_search)
    q = Query("x")
    assert (await core._one(None, "rakuma", q, True)).error == "RuntimeError: boom"
    await core._one(None, "rakuma", q, True)
    await core._one(None, "rakuma", q, True)
    assert len(calls) == 2


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/jp.mercari.com/item/m1",
        "https://jp.mercari.com.evil.example/item/m1",
        "ftp://jp.mercari.com/item/m1",
        "file:///etc/passwd",
        "https://jp.mercari.com/user/profile/1",
    ],
)
def test_listing_url_must_be_a_real_listing_on_a_known_host(url):
    with pytest.raises(ValueError, match="not a supported listing URL"):
        server.site_for_url(url)


def test_listing_url_routing():
    assert server.site_for_url(" https://JP.MERCARI.COM/item/m1?x=1 ").NAME == "mercari"
    assert server.site_for_url("https://page.auctions.yahoo.co.jp/jp/auction/x1").NAME == "yahoo"
