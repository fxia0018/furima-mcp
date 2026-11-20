# furima-mcp

[![CI](https://github.com/fxia0018/furima-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/fxia0018/furima-mcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/furima-mcp.svg)](https://pypi.org/project/furima-mcp/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

English | [日本語](README.ja.md)

<!-- mcp-name: io.github.fxia0018/furima-mcp -->

An MCP server for Japanese second-hand marketplaces. It lets Claude, Cursor or any MCP client search **Mercari**, **Yahoo! Auctions**, **Yahoo! Flea Market** (PayPay Flea Market) and **Rakuma** at once, and check what an item actually sells for.

![Claude Code calling furima-mcp to check a Switch OLED price](https://raw.githubusercontent.com/fxia0018/furima-mcp/main/docs/demo.gif)

- No browser, no login, no API key. Plain HTTP; a search across all four sites takes a few seconds.
- Prices come from **sold** listings, not asking prices: Yahoo! Auctions final bids, Mercari and Rakuma sold items.
- One site failing doesn't fail the call. Its error is reported next to the other sites' results.
- Polite by default: requests to each site are spaced at least 1 s apart, `429`/`503` responses are retried with backoff, and repeated searches are served from a 5-minute cache.

## Tools

| Tool | What it does |
| --- | --- |
| `search_listings` | Search items for sale now. Filter by site and price, sort by relevance, newest or price across all sites. |
| `sold_price_stats` | Min / p25 / median / p75 / max of recent sold prices, overall and per site, with example sales. |
| `check_price` | Where a price falls among recent sales (percentile) and a one-line verdict. |
| `get_listing` | Full details of one listing URL: description, condition, images, seller rating, auction end time. |

Every tool takes `exclude` (drop titles containing these words, e.g. `["ジャンク", "箱のみ"]`). The price tools also take `match_all_words` (on by default) because the sites' own search is fuzzy: on Mercari, `PS5 CFI-2000` also returns PS5 games, which would drag the median down to a game's price.

## Install

Needs [uv](https://docs.astral.sh/uv/).

**Claude Code**

```sh
claude mcp add furima -- uvx furima-mcp
```

**Claude Desktop, Cursor and others** — add to the client's MCP config (`claude_desktop_config.json`, `.cursor/mcp.json`, ...):

```json
{
  "mcpServers": {
    "furima": {
      "command": "uvx",
      "args": ["furima-mcp"]
    }
  }
}
```

## Things to ask

- 「ドラクエ3 SFC 箱説付き」の相場を調べて
- Find a Pokémon card "ピカチュウ 25th プロモ" under ¥5,000, cheapest first, no PSA-graded ones
- Compare what a used Sony α7 III body sells for on Yahoo! Auctions vs Mercari
- Is this a good deal? https://jp.mercari.com/item/m12345678901

Search in Japanese for best results. Product names and model numbers (`CFI-2000`, `ILCE-7M3`) match far better than English descriptions.

## Notes

- **Sold history** comes from Yahoo! Auctions' closed auctions and Rakuma's sold items (most recent first) and Mercari's sold items (best match first). Yahoo! Flea Market has no public sold history, so it only appears in `search_listings`.
- **Auction prices** (`is_auction: true`) are current bids and may still rise until `ends_at`.
- **Mercari's `sold_at`** is the item's last update time, which is normally the sale.
- **Mercari Shops** products show up in search but `get_listing` doesn't support them yet.

## Configuration

Environment variables, all optional:

| Variable | Default | Meaning |
| --- | --- | --- |
| `FURIMA_MIN_INTERVAL` | `1.0` | Minimum seconds between two requests to the same site. Raising it is fine; lowering it is not recommended. |
| `FURIMA_CACHE_TTL` | `300` | Seconds a site's search result is reused for an identical query. `0` disables the cache. |

## Responsible use

This tool reads the same public pages a person sees in a browser, one search at a time, on behalf of the person asking. It is meant for personal shopping and price research.

Please don't use it for bulk scraping, for building a database of other people's listings, or for automated buying or reselling. It carries no account, cookie or personal data, and adding any is out of scope. If a site's operator asks for something to change, open an issue and it will be handled.

## Disclaimer

furima-mcp is an independent, unofficial project. It is not affiliated with, endorsed by or sponsored by Mercari, Inc., LY Corporation, Rakuten Group, Inc. or any marketplace it reads. All product names, trademarks and listing content belong to their respective owners.

The sites can change or restrict access at any time, and results may be incomplete, delayed or wrong. Prices and verdicts are informational, not financial or purchasing advice; check the listing itself before you buy. You are responsible for complying with each site's terms of service and the laws that apply to you. The software is provided as is, without warranty of any kind; see [LICENSE](LICENSE).

## Development

```sh
git clone https://github.com/fxia0018/furima-mcp && cd furima-mcp
uv sync
uv run pytest            # offline tests against hand-written page fixtures
uv run pytest -m live    # one smoke test against the real sites
```

Each site is one module in `src/furima_mcp/sites/` with a `search(client, query)` and an `item(client, url)`. Adding a site means adding a module there and registering it in `sites/__init__.py`.

## License

MIT
