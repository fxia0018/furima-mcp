import pytest

from furima_mcp import watch
from furima_mcp.models import Listing, Query, SiteResult


def timed(id, minute):
    return Listing(
        site="mercari", id=id, title="t", price=1, url="u", listed_at=f"2026-11-20T12:{minute:02d}:00+09:00"
    )


def numbered(id, seq):
    return Listing(site="rakuma", id=id, title="t", price=1, url="u", seq=seq)


Q = Query("switch", conditions=("new",))


def roundtrip(marks):
    return watch.decode(watch.encode(Q, marks), Q)


def test_first_check_returns_everything_and_marks_the_newest():
    new, marks, gaps = watch.check([SiteResult("mercari", [timed("b", 5), timed("a", 1)])], None)
    assert [l.id for l in new["mercari"]] == ["b", "a"]
    assert roundtrip(marks)["mercari"]["ids"] == ["b"]
    assert gaps == []


def test_next_check_returns_only_newer_listings():
    _, marks, _ = watch.check([SiteResult("mercari", [timed("b", 5), timed("a", 1)])], None)
    later = SiteResult("mercari", [timed("d", 9), timed("c", 5), timed("b", 5), timed("a", 1)])
    new, marks, gaps = watch.check([later], roundtrip(marks))
    # "c" shares b's minute but was not seen before
    assert [l.id for l in new["mercari"]] == ["d", "c"]
    assert gaps == []
    new, _, _ = watch.check([later], roundtrip(marks))
    assert new["mercari"] == []


def test_rakuma_uses_growing_item_numbers():
    _, marks, _ = watch.check([SiteResult("rakuma", [numbered("x", 100), numbered("y", 90)])], None)
    # an old listing bumped to the top keeps its old number and is not new
    later = SiteResult("rakuma", [numbered("z", 101), numbered("old", 50), numbered("x", 100)])
    new, _, _ = watch.check([later], roundtrip(marks))
    assert [l.id for l in new["rakuma"]] == ["z"]


def test_failed_site_keeps_its_mark():
    _, marks, _ = watch.check([SiteResult("mercari", [timed("a", 1)])], None)
    _, marks, _ = watch.check([SiteResult("mercari", error="HTTP 503")], roundtrip(marks))
    new, _, _ = watch.check([SiteResult("mercari", [timed("b", 2), timed("a", 1)])], roundtrip(marks))
    assert [l.id for l in new["mercari"]] == ["b"]


def test_whole_page_new_is_reported_as_a_possible_gap():
    _, marks, _ = watch.check([SiteResult("mercari", [timed("a", 1)])], None)
    new, _, gaps = watch.check([SiteResult("mercari", [timed("c", 3), timed("b", 2)])], roundtrip(marks))
    assert len(new["mercari"]) == 2 and gaps == ["mercari"]


def test_site_added_later_starts_without_flooding():
    _, marks, _ = watch.check([SiteResult("mercari", [timed("a", 1)])], None)
    new, marks, _ = watch.check(
        [SiteResult("mercari", [timed("a", 1)]), SiteResult("rakuma", [numbered("x", 5)])], roundtrip(marks)
    )
    assert new == {"mercari": [], "rakuma": []}
    assert "rakuma" in marks


def test_bad_or_foreign_cursors_are_rejected():
    with pytest.raises(ValueError, match="invalid cursor"):
        watch.decode("not-a-cursor", Q)
    with pytest.raises(ValueError, match="invalid cursor"):
        watch.decode(watch.encode(Q, {"mercari": {"m": "x", "ids": []}}), Q)
    with pytest.raises(ValueError, match="different query"):
        watch.decode(watch.encode(Q, {}), Query("switch"))
