"""Stateless watching: which listings went up since the last check.

The server keeps nothing between calls. Each check returns a cursor that records, per
site, the newest listing seen; the next check passes it back and gets only what is newer.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json

from .models import Listing, Query, SiteResult

VERSION = 1


def search_key(q: Query) -> str:
    """Ties a cursor to the search it came from."""
    raw = json.dumps([q.keyword, sorted(q.conditions)], ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def marker(listing: Listing) -> float | None:
    """A number that grows with listing time: the listing timestamp, or Rakuma's item id."""
    if listing.listed_at:
        try:
            return dt.datetime.fromisoformat(listing.listed_at.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return float(listing.seq) if listing.seq is not None else None


def mark_of(listings: list[Listing]) -> dict | None:
    """The newest marker in a result, and the ids that share it."""
    marked = [(m, l.id) for l in listings if (m := marker(l)) is not None]
    if not marked:
        return None
    top = max(m for m, _ in marked)
    return {"m": top, "ids": sorted({i for m, i in marked if m == top})}


def is_new(listing: Listing, mark: dict) -> bool:
    m = marker(listing)
    if m is None:
        return False
    return m > mark["m"] or (m == mark["m"] and listing.id not in mark["ids"])


def encode(q: Query, marks: dict[str, dict]) -> str:
    state = {"v": VERSION, "q": search_key(q), "sites": marks}
    raw = json.dumps(state, separators=(",", ":"), ensure_ascii=False).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode(cursor: str, q: Query) -> dict[str, dict]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        state = json.loads(raw)
        marks = state["sites"]
        ok = state.get("v") == VERSION and isinstance(marks, dict)
        ok = ok and all(
            isinstance(m, dict) and isinstance(m.get("m"), (int, float)) and isinstance(m.get("ids"), list)
            for m in marks.values()
        )
    except (ValueError, KeyError, TypeError):
        ok = False
    if not ok:
        raise ValueError("invalid cursor; call without one to start a new watch")
    if state.get("q") != search_key(q):
        raise ValueError("this cursor belongs to a different query or condition filter")
    return marks


def check(results: list[SiteResult], previous: dict[str, dict] | None) -> tuple[dict, dict, list[str]]:
    """Split each site's newest-first results into what is new since `previous`.

    Returns the new listings per site, the marks for the next cursor, and the sites whose
    whole page was new (more may have gone up than one page shows).
    """
    new: dict[str, list[Listing]] = {}
    marks: dict[str, dict] = {}
    gaps: list[str] = []
    for r in results:
        before = (previous or {}).get(r.site)
        now = mark_of(r.listings)
        # Keep the old mark when a site failed or came back empty, so nothing is skipped.
        if now and before and now["m"] == before["m"]:
            now["ids"] = sorted(set(now["ids"]) | set(before["ids"]))
        site_mark = now if now and (not before or now["m"] >= before["m"]) else before
        if site_mark:
            marks[r.site] = site_mark
        if before is None:
            new[r.site] = [] if previous is not None else list(r.listings)
            continue
        fresh = [l for l in r.listings if is_new(l, before)]
        new[r.site] = fresh
        if fresh and len(fresh) == len(r.listings):
            gaps.append(r.site)
    return new, marks, gaps
