# Changelog

## 0.1.0 (unreleased)

- Tools: `search_listings`, `sold_price_stats`, `check_price`, `get_listing`.
- Sites: Mercari, Yahoo! Auctions, Yahoo! Flea Market, Rakuma.
- Per-site request spacing, retry with backoff on `429`/`503`, and a 5-minute result cache.
- `get_listing` only accepts listing URLs on the supported hosts and requests each site's canonical URL.
