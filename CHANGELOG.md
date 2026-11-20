# Changelog

## 0.2.0 (2026-11-20)

- Item condition: every listing carries its condition (`new`, `like_new`, `good`, `fair`, `poor`, `bad`), every search tool takes `conditions`, and `sold_price_stats` adds `by_condition`.
- New tool `new_listings`: watch a search for listings put up since the last check, with a stateless cursor.
- Yahoo! Flea Market items returned by the Yahoo! Auctions search are now labelled `paypay` and no longer appear twice. Their sold prices count toward the `paypay` site in the stats.
- Yahoo! Flea Market `newest` sort now really sorts by listing time.
- Server instructions tell the model that listing text is untrusted.
- GitHub releases are created from this changelog; bug and feature issue templates.

## 0.1.1 (2026-11-20)

- `furima-mcp --help` and `--version`. Running it by hand in a terminal now prints a hint instead of waiting silently.
- README: demo GIF.

## 0.1.0 (2026-11-19)

- Tools: `search_listings`, `sold_price_stats`, `check_price`, `get_listing`.
- Sites: Mercari, Yahoo! Auctions, Yahoo! Flea Market, Rakuma.
- Per-site request spacing, retry with backoff on `429`/`503`, and a 5-minute result cache.
- `get_listing` only accepts listing URLs on the supported hosts and requests each site's canonical URL.
