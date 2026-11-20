import base64
import json

import httpx
import respx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from furima_mcp.models import Query
from furima_mcp.sites import mercari, paypay, rakuma, yahoo

from . import fixtures as fx


def test_yahoo_live_marks_real_auctions_only():
    listings, total = yahoo.parse_search(fx.yahoo_search(fx.YAHOO_LIVE_ITEMS, 2), sold=False)
    assert total == 2
    a, b = listings
    assert (a.id, a.title, a.price, a.is_auction, a.bids) == ("x100", "テスト ぬいぐるみ A", 1200, True, 3)
    assert a.ends_at == "2026-11-20T21:00:00+09:00" and a.sold_at is None
    assert a.url == "https://auctions.yahoo.co.jp/jp/auction/x100"
    assert (a.condition, a.listed_at) == ("good", "2026-11-18T21:00:00+09:00")
    # a Yahoo! Flea Market item surfaced in Yahoo search is labelled as one, not an auction
    assert (b.site, b.id, b.condition) == ("paypay", "x101", "new")
    assert b.url == "https://paypayfleamarket.yahoo.co.jp/item/x101"
    assert b.is_auction is False and b.bids is None


def test_yahoo_closed_uses_end_time_as_sold_at():
    listings, _ = yahoo.parse_search(fx.yahoo_search(fx.YAHOO_CLOSED_ITEMS, 2, "/closedsearch"), sold=True)
    assert [(l.price, l.sold, l.is_auction) for l in listings] == [(3000, True, False), (4000, True, False)]
    assert listings[0].sold_at == "2026-11-18T20:00:00+09:00" and listings[0].ends_at is None


def test_yahoo_unknown_page_is_empty():
    assert yahoo.parse_search("<html>maintenance</html>", sold=False) == ([], None)


def test_yahoo_search_url():
    q = Query("ピカチュウ ぬいぐるみ", sort="price_asc", min_price=500, max_price=900)
    url = yahoo.search_url(q, offset=101)
    assert url.startswith("https://auctions.yahoo.co.jp/search/search?")
    assert "b=101" in url and "s1=cbids&o1=a" in url and "aucminprice=500" in url and "aucmaxprice=900" in url
    sold = yahoo.search_url(Query("x", sold=True))
    assert "closedsearch/closedsearch" in sold and "s1=" not in sold


def test_yahoo_item():
    d = yahoo.parse_item(fx.YAHOO_ITEM)
    assert d["price"] == 1200 and d["buy_now_price"] == 5000 and d["status"] == "open"
    assert d["description"] == "一行目\n二行目" and d["images"] == ["https://img.example/1.jpg"]
    assert d["seller"]["id"] == "seller1" and d["auto_extension"] is True


def test_paypay_search_and_item():
    listings, total = paypay.parse_search(fx.paypay_search(fx.PAYPAY_ITEMS, 1))
    assert total == 1
    (l,) = listings
    assert (l.id, l.price, l.listed_at) == ("z1", 900, "2026-11-19T10:00:00+09:00")
    assert l.url == "https://paypayfleamarket.yahoo.co.jp/item/z1"
    d = paypay.parse_item(fx.PAYPAY_ITEM)
    assert d["status"] == "sold" and d["condition"] == "未使用" and d["seller"]["name"] == "nick"


def test_paypay_search_url_quotes_keyword_in_path():
    url = paypay.search_url(Query("a b/c", sort="price_desc"), page=2)
    assert url.startswith("https://paypayfleamarket.yahoo.co.jp/search/a%20b%2Fc?open=1")
    assert "sort=price&order=desc" in url and "page=2" in url


async def test_paypay_has_no_sold_history():
    res = await paypay.search(None, Query("x", sold=True))
    assert res.listings == [] and res.error is None


def test_rakuma_cards_dedup_unescape_and_sold():
    listings, total = rakuma.parse_search(fx.RAKUMA_SEARCH)
    assert total == 2
    assert [(l.id, l.title, l.price, l.sold) for l in listings] == [
        ("aaa111", "テスト & ぬいぐるみ D", 1500, False),
        ("bbb222", "テスト ぬいぐるみ E", 800, True),
    ]
    assert listings[0].image == "https://img.fril.jp/img/aaa111.jpg"


def test_rakuma_search_url():
    url = rakuma.search_url(Query("x", sold=True), page=3)
    assert "transaction=soldout" in url and "sort=created_at" in url and "page=3" in url


def test_rakuma_item_trusts_sold_badge_over_json_ld():
    d = rakuma.parse_item(fx.RAKUMA_ITEM, "https://item.fril.jp/aaa111")
    assert d["status"] == "sold" and d["condition"] == "未使用に近い" and d["price"] == 1500


def test_mercari_parse_search():
    a, b = mercari.parse_search(fx.MERCARI_SEARCH)
    assert (a.url, a.price, a.sold, a.sold_at) == ("https://jp.mercari.com/item/m111", 3000, False, None)
    assert a.listed_at.startswith("2026-") and a.listed_at.endswith("+09:00")
    assert b.url == "https://jp.mercari.com/shops/product/Shop1" and b.sold and b.sold_at


def test_mercari_search_body():
    body = mercari.search_body(Query("x", sold=True, sort="price_asc", min_price=100, max_price=200), "v1:1")
    cond = body["searchCondition"]
    assert cond["status"] == ["STATUS_SOLD_OUT", "STATUS_TRADING"]
    assert (cond["sort"], cond["order"]) == ("SORT_PRICE", "ORDER_ASC")
    assert (cond["priceMin"], cond["priceMax"], body["pageToken"]) == (100, 200, "v1:1")


def test_mercari_item():
    d = mercari.parse_item(fx.MERCARI_ITEM)
    assert d["status"] == "on_sale" and d["condition"] == "未使用に近い" and d["seller"]["id"] == "42"


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def test_mercari_dpop_proof_verifies():
    token = mercari._DPoP().proof("POST", mercari.SEARCH_URL)
    head, body, sig = token.split(".")
    header, payload = json.loads(_unb64(head)), json.loads(_unb64(body))
    assert header["typ"] == "dpop+jwt" and header["alg"] == "ES256"
    assert payload["htm"] == "POST" and payload["htu"] == mercari.SEARCH_URL
    jwk = header["jwk"]
    pub = ec.EllipticCurvePublicNumbers(
        int.from_bytes(_unb64(jwk["x"]), "big"), int.from_bytes(_unb64(jwk["y"]), "big"), ec.SECP256R1()
    ).public_key()
    raw = _unb64(sig)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    pub.verify(der, f"{head}.{body}".encode(), ec.ECDSA(hashes.SHA256()))  # raises if invalid


def test_item_url_patterns():
    assert mercari.ITEM_URL_PATTERN.search("https://jp.mercari.com/item/m123?source=x").group(2) == "m123"
    assert mercari.ITEM_URL_PATTERN.search("https://jp.mercari.com/en/item/m123").group(2) == "m123"
    assert yahoo.ITEM_URL_PATTERN.search("https://auctions.yahoo.co.jp/jp/auction/x100").group(1) == "x100"
    assert paypay.ITEM_URL_PATTERN.search("https://paypayfleamarket.yahoo.co.jp/item/z1").group(1) == "z1"
    assert rakuma.ITEM_URL_PATTERN.search("https://item.fril.jp/aaa111").group(1) == "aaa111"


def test_conditions_parsed_on_every_site():
    assert mercari.parse_search(fx.MERCARI_SEARCH)[0].condition == "like_new"
    assert mercari.parse_search(fx.MERCARI_SEARCH)[1].condition is None  # no id given
    closed, _ = yahoo.parse_search(fx.yahoo_search(fx.YAHOO_CLOSED_ITEMS, 2, "/closedsearch"), sold=True)
    assert [l.condition for l in closed] == ["new", "fair"]
    (p,), _ = paypay.parse_search(fx.paypay_search(fx.PAYPAY_ITEMS, 1))
    assert p.condition == "like_new"
    cards, _ = rakuma.parse_search(fx.RAKUMA_SEARCH)
    assert [(c.condition, c.seq) for c in cards] == [(None, 1002), (None, 1001)]
    assert "seq" not in cards[0].to_dict()


def test_condition_filters_in_search_requests():
    both = Query("x", conditions=("new", "like_new"))
    assert mercari.search_body(both)["searchCondition"]["itemConditionId"] == [1, 2]
    assert "itemConditionId" not in mercari.search_body(Query("x"))["searchCondition"]
    assert "conditions=NEW%2CUSED10" in paypay.search_url(both)
    # Yahoo's search only splits new from used; the rest is filtered after parsing.
    assert "istatus=1" in yahoo.search_url(Query("x", conditions=("new",)))
    assert "istatus=2" in yahoo.search_url(Query("x", conditions=("good", "fair")))
    assert "istatus" not in yahoo.search_url(both)
    assert "status=5" in rakuma.search_url(Query("x"), condition="new")
    assert "status" not in rakuma.search_url(Query("x"))


def test_paypay_newest_sorts_by_open_time():
    assert "sort=openTime&order=desc" in paypay.search_url(Query("x", sort="newest"))


async def test_rakuma_searches_once_per_condition_and_tags_listings():
    with respx.mock() as mock:
        new = mock.get(url__regex=r"fril\.jp/s\?.*status=5").respond(
            text=fx.rakuma_card("n1", "テスト 新品", 3000, seq=2)
        )
        used = mock.get(url__regex=r"fril\.jp/s\?.*status=6").respond(
            text=fx.rakuma_card("u1", "テスト 中古", 2000, seq=1)
        )
        async with httpx.AsyncClient() as client:
            res = await rakuma.search(client, Query("x", sort="price_asc", conditions=("new", "good")))
    assert new.called and used.called
    assert [(l.id, l.condition) for l in res.listings] == [("u1", "good"), ("n1", "new")]
