"""Hand-written, minimal copies of each site's page shapes (no real listings)."""

import json


def next_data_page(payload: dict) -> str:
    return (
        "<html><head></head><body>"
        f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload, ensure_ascii=False)}</script>'
        "</body></html>"
    )


def yahoo_search(items: list[dict], total: int, page: str = "/search/search") -> str:
    return next_data_page(
        {
            "page": page,
            "props": {
                "pageProps": {
                    "initialState": {
                        "search": {"items": {"listing": {"items": items, "totalResultsAvailable": total}}}
                    }
                }
            },
        }
    )


YAHOO_LIVE_ITEMS = [
    {
        "auctionId": "x100",
        "title": "テスト ぬいぐるみ A ",
        "price": 1200,
        "imageUrl": "https://img.example/a.jpg",
        "endTime": "2026-11-20T21:00:00+09:00",
        "bidCount": 3,
    },
    {
        "auctionId": "x101",
        "title": "テスト ぬいぐるみ B",
        "price": 2500,
        "endTime": "2026-12-01T21:00:00+09:00",
        "isFleamarketItem": True,
        "bidCount": 0,
    },
]

YAHOO_CLOSED_ITEMS = [
    {"auctionId": "c1", "title": "落札品 1", "price": 3000, "endTime": "2026-11-18T20:00:00+09:00"},
    {"auctionId": "c2", "title": "落札品 2", "price": "4,000", "endTime": "2026-11-17T20:00:00+09:00"},
]

YAHOO_ITEM = next_data_page(
    {
        "props": {
            "pageProps": {
                "initialState": {
                    "item": {
                        "detail": {
                            "item": {
                                "auctionId": "x100",
                                "title": "テスト ぬいぐるみ A",
                                "price": 1200,
                                "bidorbuy": 5000,
                                "bids": 3,
                                "status": "open",
                                "endTime": "2026-11-20T21:00:00+09:00",
                                "isAutomaticExtension": True,
                                "conditionName": "目立った傷や汚れなし",
                                "description": ["一行目", "二行目"],
                                "img": [{"image": "https://img.example/1.jpg"}],
                                "seller": {
                                    "aucUserId": "seller1",
                                    "rating": {"goodRating": "99.0%", "summary": 120},
                                    "isStore": False,
                                },
                            }
                        }
                    }
                }
            }
        }
    }
)


def paypay_search(items: list[dict], total: int) -> str:
    return next_data_page(
        {
            "props": {
                "initialState": {
                    "searchState": {"search": {"result": {"items": items, "totalResultsAvailable": total}}}
                }
            }
        }
    )


PAYPAY_ITEMS = [
    {
        "id": "z1",
        "title": "テスト ぬいぐるみ C",
        "price": 900,
        "thumbnailImageUrl": "https://img.example/c.jpg",
        "openTime": "2026-11-19T10:00:00+09:00",
    },
]

PAYPAY_ITEM = next_data_page(
    {
        "props": {
            "initialState": {
                "itemsState": {
                    "items": {
                        "item": {
                            "id": "z1",
                            "title": "テスト ぬいぐるみ C",
                            "price": 900,
                            "status": "SOLD",
                            "condition": {"key": "new", "text": "未使用"},
                            "description": "説明",
                            "images": [{"url": "https://img.example/c1.jpg"}],
                            "likeCount": 4,
                            "seller": {
                                "id": "p1",
                                "nickname": "nick",
                                "rating": {"total": 10, "goodRatio": 100},
                            },
                        }
                    }
                }
            }
        }
    }
)


def rakuma_card(item_id: str, name: str, price: int, status: str = "販売中") -> str:
    return f"""
  <div class="item"><div class="item-box">
    <a href="https://item.fril.jp/{item_id}" class="link_search_image"
       title="{name} (おもちゃ)の商品詳細ページへのリンク"
       onclick="ga('send')" data-rat-itemid="777/{item_id}" data-rat-item_name="{name}"
       data-rat-price="{price}" data-rat-cp-search_sales_status="{status}"
       data-rat-cp-totalresults="2">
      <img src="https://asset.fril.jp/dummy.png" data-original="https://img.fril.jp/img/{item_id}.jpg" alt="{name}">
    </a>
    <a href="https://item.fril.jp/{item_id}" class="link_search_title">{name}</a>
  </div></div>"""


RAKUMA_SEARCH = (
    "<html><body>"
    + rakuma_card("aaa111", "テスト &amp; ぬいぐるみ D", 1500)
    + rakuma_card("bbb222", "テスト ぬいぐるみ E", 800, "売り切れ")
    + "</body></html>"
)

RAKUMA_ITEM = """<html><head>
<script type="application/ld+json">{"@context":"http://schema.org/","@type":"Product","name":"テスト ぬいぐるみ D",
"image":"https://img.fril.jp/img/aaa111.jpg","description":"説明文",
"offers":{"@type":"Offer","priceCurrency":"JPY","price":1500,"availability":"http://schema.org/InStock",
"seller":{"@type":"Organization","name":"seller"}}}</script></head><body>
<table><tr>
  <th><i class="icon-status icon_item_status item-status-status"></i> 商品の状態</th>
  <td>未使用に近い</td>
</tr></table>
<span>SOLD OUT</span>
</body></html>"""

MERCARI_SEARCH = {
    "meta": {"nextPageToken": "", "numFound": "2"},
    "items": [
        {
            "id": "m111",
            "name": "テスト ぬいぐるみ F",
            "price": "3000",
            "status": "ITEM_STATUS_ON_SALE",
            "created": "1795000000",
            "updated": "1795000100",
            "thumbnails": ["https://static.example/m111.jpg"],
            "itemType": "ITEM_TYPE_MERCARI",
        },
        {
            "id": "Shop1",
            "name": "ショップ商品",
            "price": "5000",
            "status": "ITEM_STATUS_SOLD_OUT",
            "created": "1795000000",
            "updated": "1795003600",
            "thumbnails": [],
            "itemType": "ITEM_TYPE_BEYOND",
        },
    ],
}

MERCARI_ITEM = {
    "data": {
        "id": "m111",
        "name": "テスト ぬいぐるみ F",
        "price": 3000,
        "status": "on_sale",
        "item_condition": {"id": 2, "name": "未使用に近い"},
        "shipping_payer": {"id": 2, "code": "seller"},
        "description": "説明",
        "photos": ["https://static.example/m111_1.jpg"],
        "num_likes": 5,
        "created": 1795000000,
        "updated": 1795000100,
        "seller": {"id": 42, "name": "seller", "ratings": {"good": 10, "normal": 0, "bad": 1}},
    }
}
