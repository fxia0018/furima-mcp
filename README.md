# furima-mcp

An MCP server for Japanese second-hand marketplaces. It lets Claude, Cursor or any MCP client search **Mercari**, **Yahoo! Auctions**, **Yahoo! Flea Market** (PayPay Flea Market) and **Rakuma** at once, and check what an item actually sells for.

> **You:** Is ¥30,000 a good price for a Switch OLED?
>
> **Claude:** *(calls `check_price`)* Not really. Across 214 recent sales on Mercari, Yahoo! Auctions and Rakuma the median was ¥25,000 and the middle half sold for ¥22,000–28,000. ¥30,000 is dearer than 82% of them.

- No browser, no login, no API key. Plain HTTP; a search across all four sites takes a few seconds.
- Prices come from **sold** listings, not asking prices: Yahoo! Auctions final bids, Mercari and Rakuma sold items.
- One site failing doesn't fail the call. Its error is reported next to the other sites' results.

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
claude mcp add furima -- uvx --from git+https://github.com/fxia0018/furima-mcp furima-mcp
```

**Claude Desktop, Cursor and others** — add to the client's MCP config (`claude_desktop_config.json`, `.cursor/mcp.json`, ...):

```json
{
  "mcpServers": {
    "furima": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/fxia0018/furima-mcp", "furima-mcp"]
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
- This is an unofficial tool that reads public pages. Keep request volume reasonable and follow each site's terms of use. If a site changes its pages, the affected site returns an error until the parser is updated; issues and PRs welcome.

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
