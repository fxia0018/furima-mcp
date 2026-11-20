import pytest

from furima_mcp.core import has_all_words, merge, percentile_of, pick_sites, price_stats, verdict
from furima_mcp.models import Listing, Query, SiteResult


def L(site, price, title="item"):
    return Listing(site=site, id=f"{site}{price}", title=title, price=price, url="u")


def test_has_all_words_folds_width_case_and_hyphens():
    assert has_all_words("PlayStation5 ＰＳ５ 本体 cfi2000a01", "PS5 CFI-2000")
    assert has_all_words("ポケモンカード・ピカチュウ", "ポケモンカード ピカチュウ")
    assert not has_all_words("PS5 ソフト ウルヴァリン", "PS5 CFI-2000")


def test_merge_interleaves_sites_for_relevance():
    results = [SiteResult("a", [L("a", 1), L("a", 2), L("a", 3)]), SiteResult("b", [L("b", 9)])]
    assert [l.id for l in merge(results, Query("x"), None)] == ["a1", "b9", "a2", "a3"]


def test_merge_sorts_by_price_across_sites_and_filters():
    results = [
        SiteResult("a", [L("a", 300), L("a", 100, "ジャンク品"), L("a", 50)]),
        SiteResult("b", [L("b", 200), Listing("b", "n", "no price", None, "u")]),
    ]
    q = Query("x", sort="price_asc", min_price=60)
    assert [l.price for l in merge(results, q, ["じゃんく", "ジャンク"])] == [200, 300]


def test_merge_match_all_words():
    results = [SiteResult("a", [L("a", 1, "PS5 本体 CFI-2000"), L("a", 2, "PS5 ソフト")])]
    assert [l.price for l in merge(results, Query("PS5 CFI-2000"), None, match_all=True)] == [1]


def test_price_stats():
    assert price_stats([]) == {"count": 0}
    s = price_stats([100, 200, 300, 400, 500])
    assert (s["count"], s["min"], s["p25"], s["median"], s["p75"], s["max"], s["mean"]) == (
        5,
        100,
        200,
        300,
        400,
        500,
        300,
    )
    assert price_stats([700])["median"] == 700


def test_percentile_and_verdict():
    prices = [100, 200, 300, 400]
    assert percentile_of(50, prices) == 0
    assert percentile_of(250, prices) == 50
    assert percentile_of(200, prices) == 37.5
    assert verdict(5, 100).startswith("very cheap")
    assert verdict(50, 100).startswith("typical")
    assert verdict(95, 100).startswith("very expensive")
    assert verdict(5, 3) == "not enough sold data to judge"


def test_pick_sites():
    assert pick_sites(None, sold=True) == ["mercari", "yahoo", "rakuma"]
    assert pick_sites(["paypay", "yahoo"], sold=True) == ["yahoo"]
    with pytest.raises(ValueError, match="unknown site"):
        pick_sites(["ebay"], sold=False)


def test_merge_keeps_only_requested_conditions():
    good, fair, unknown = L("mercari", 1), L("mercari", 2), L("mercari", 3)
    good.condition, fair.condition = "good", "fair"
    q = Query("item", conditions=("good",))
    assert merge([SiteResult("mercari", [good, fair, unknown])], q, None) == [good]


def test_merge_drops_flea_market_duplicates_from_yahoo():
    # Yahoo! Auctions returns Yahoo! Flea Market items under the paypay label and same id.
    from_paypay = Listing(site="paypay", id="z1", title="item", price=500, url="u")
    via_yahoo = Listing(site="paypay", id="z1", title="item", price=500, url="u")
    out = merge(
        [SiteResult("yahoo", [via_yahoo, L("yahoo", 900)]), SiteResult("paypay", [from_paypay])],
        Query("item"),
        None,
    )
    assert sorted((l.site, l.id) for l in out) == [("paypay", "z1"), ("yahoo", "yahoo900")]
