"""Fan a query out to the sites and summarize the results."""

from __future__ import annotations

import asyncio
import os
import re
import statistics
import time
import unicodedata
from dataclasses import astuple
from itertools import chain, zip_longest

import httpx

from .models import Listing, Query, SiteResult
from .sites import SITES, SOLD_SITES

SITE_TIMEOUT = 60.0
# Agents often repeat a search while refining a question; serve those from memory.
CACHE_TTL = float(os.environ.get("FURIMA_CACHE_TTL", "300"))
CACHE_MAX = 256
_cache: dict[tuple, tuple[float, SiteResult]] = {}


def pick_sites(sites: list[str] | None, sold: bool) -> list[str]:
    allowed = SOLD_SITES if sold else tuple(SITES)
    if not sites:
        return list(allowed)
    unknown = [s for s in sites if s not in SITES]
    if unknown:
        raise ValueError(f"unknown site(s): {', '.join(unknown)}; choose from {', '.join(SITES)}")
    return [s for s in sites if s in allowed]


async def _one(client: httpx.AsyncClient, site: str, q: Query, use_cache: bool) -> SiteResult:
    key = (site, *astuple(q))
    hit = _cache.get(key) if use_cache else None
    if hit and time.monotonic() - hit[0] < CACHE_TTL:
        return hit[1]
    try:
        result = await asyncio.wait_for(SITES[site].search(client, q), SITE_TIMEOUT)
    except asyncio.TimeoutError:
        return SiteResult(site=site, error="timed out")
    except httpx.HTTPStatusError as e:
        return SiteResult(site=site, error=f"HTTP {e.response.status_code}")
    except Exception as e:  # one broken site must not sink the others
        return SiteResult(site=site, error=f"{type(e).__name__}: {e}")
    if len(_cache) >= CACHE_MAX:  # drop the oldest entry; failures are never cached
        _cache.pop(min(_cache, key=lambda k: _cache[k][0]))
    _cache[key] = (time.monotonic(), result)
    return result


async def search_sites(
    client: httpx.AsyncClient, sites: list[str], q: Query, use_cache: bool = True
) -> list[SiteResult]:
    return list(await asyncio.gather(*(_one(client, s, q, use_cache) for s in sites)))


_PUNCT = re.compile(r"[\s\-_・/･.,、。]+")


def normalize(text: str) -> str:
    """Fold width, case and separators: "ＣＦＩ－２０００" and "cfi2000" compare equal."""
    return _PUNCT.sub("", unicodedata.normalize("NFKC", text).casefold())


def has_all_words(title: str, keyword: str) -> bool:
    norm = normalize(title)
    return all(normalize(w) in norm for w in unicodedata.normalize("NFKC", keyword).split())


def keep(listing: Listing, exclude: list[str] | None, q: Query, match_all: bool = False) -> bool:
    if listing.price is None or listing.sold != q.sold:
        return False
    if q.conditions and listing.condition not in q.conditions:
        return False
    # Sites treat price bounds loosely (Yahoo compares the buy-now price, not the bid).
    if q.min_price and listing.price < q.min_price:
        return False
    if q.max_price and listing.price > q.max_price:
        return False
    if match_all and not has_all_words(listing.title, q.keyword):
        return False
    title = normalize(listing.title)
    return not any(normalize(w) in title for w in exclude or [] if normalize(w))


def merge(
    results: list[SiteResult], q: Query, exclude: list[str] | None, match_all: bool = False
) -> list[Listing]:
    """Filter each site's listings, then combine them in the order `q.sort` asks for."""
    # Yahoo! Auctions also returns Yahoo! Flea Market items (labelled paypay, same id) that
    # the paypay search finds too; keep one copy.
    seen: set[tuple[str, str]] = set()
    per_site = []
    for r in results:
        rows = []
        for l in r.listings:
            if (l.site, l.id) not in seen and keep(l, exclude, q, match_all):
                seen.add((l.site, l.id))
                rows.append(l)
        per_site.append(rows)
    if q.sort == "price_asc":
        return sorted(chain(*per_site), key=lambda l: l.price)
    if q.sort == "price_desc":
        return sorted(chain(*per_site), key=lambda l: -l.price)
    # Relevance and newest are each site's own ranking; interleave so no site is buried.
    return [l for row in zip_longest(*per_site) for l in row if l is not None]


def price_stats(prices: list[int]) -> dict:
    if not prices:
        return {"count": 0}
    prices = sorted(prices)
    out = {"count": len(prices), "min": prices[0], "max": prices[-1]}
    if len(prices) >= 2:
        q1, med, q3 = statistics.quantiles(prices, n=4, method="inclusive")
        out.update(p25=round(q1), median=round(med), p75=round(q3))
    else:
        out.update(p25=prices[0], median=prices[0], p75=prices[0])
    out["mean"] = round(statistics.fmean(prices))
    return out


OUTLIER_MIN_COUNT = 8  # below this, quartiles are too unstable to call anything an outlier


def split_outliers(prices: list[int]) -> tuple[list[int], list[int]]:
    """Split prices into (kept, outliers) with Tukey's fences (1.5 IQR beyond the quartiles).

    Keyword matches on sold listings pull in accessories and parts (far below) and bulk
    lots or misattributed models (far above). Small samples are returned unchanged.
    """
    if len(prices) < OUTLIER_MIN_COUNT:
        return list(prices), []
    q1, _, q3 = statistics.quantiles(prices, n=4, method="inclusive")
    lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
    kept = [p for p in prices if lo <= p <= hi]
    return kept, [p for p in prices if not lo <= p <= hi]


def robust_stats(prices: list[int], drop_outliers: bool) -> dict:
    """price_stats, after dropping outliers when asked; says how many were dropped."""
    if not drop_outliers:
        return price_stats(prices)
    kept, out = split_outliers(prices)
    stats = price_stats(kept)
    if out:
        stats["outliers_dropped"] = len(out)
    return stats


def sold_between(listings: list[Listing]) -> dict | None:
    """Oldest and newest sale date among listings that carry one (Rakuma shows none)."""
    dates = sorted(l.sold_at[:10] for l in listings if l.sold_at)
    if not dates:
        return None
    return {"oldest": dates[0], "newest": dates[-1], "dated": len(dates)}


def percentile_of(price: int, prices: list[int]) -> float | None:
    """Share of prices strictly below `price`, plus half of the ties, in percent."""
    if not prices:
        return None
    below = sum(p < price for p in prices)
    ties = sum(p == price for p in prices)
    return round(100 * (below + ties / 2) / len(prices), 1)


def verdict(pct: float | None, count: int) -> str:
    if pct is None or count < 5:
        return "not enough sold data to judge"
    if pct <= 10:
        return "very cheap: below 90% of recent sales; check condition and authenticity"
    if pct <= 25:
        return "cheap: in the bottom quarter of recent sales"
    if pct < 75:
        return "typical: within the middle half of recent sales"
    if pct < 90:
        return "expensive: in the top quarter of recent sales"
    return "very expensive: above 90% of recent sales"


def errors_of(results: list[SiteResult]) -> dict:
    return {r.site: r.error for r in results if r.error}
