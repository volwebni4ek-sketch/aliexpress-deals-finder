import json

import pytest

from aliexpress_deals.providers.base import AntiBotChallengeError
from aliexpress_deals.providers.web_search import extract_init_data_json, parse_search_items


def test_extract_and_parse_init_data_html() -> None:
    payload = {
        "data": {
            "root": {
                "fields": {
                    "mods": {
                        "itemList": {
                            "content": [
                                {
                                    "productId": "100500999888",
                                    "title": {"displayTitle": "USB-C 100W GaN Charger"},
                                    "prices": {
                                        "salePrice": {"minPrice": 18.50, "currencyCode": "USD"},
                                        "originalPrice": {"minPrice": 37.00},
                                    },
                                    "evaluation": {"starRating": 4.8},
                                    "trade": {"tradeDesc": "1,200+ sold"},
                                    "store": {"storeName": "Baseus Official"},
                                    "image": {"imgUrl": "//ae01.alicdn.com/kf/example.jpg"},
                                    "sellingPoints": [
                                        {"tagContent": {"tagText": "Free shipping"}},
                                        {"tagContent": {"tagText": "Save $2 off $15"}},
                                    ],
                                }
                            ]
                        }
                    }
                }
            }
        }
    }
    html = f"<html><script>window._d_c_={{}}; _init_data_={json.dumps(payload)};</script></html>"

    extracted = extract_init_data_json(html)
    deals = parse_search_items(extracted)

    assert len(deals) == 1
    deal = deals[0]
    assert deal.product_id == "100500999888"
    assert deal.title == "USB-C 100W GaN Charger"
    assert deal.sale_price == 18.50
    assert deal.original_price == 37.00
    assert deal.discount_pct == 50.0
    assert deal.free_shipping is True
    assert deal.total_cost == 18.50
    assert deal.orders_count == 1200
    assert deal.rating == 4.8
    assert deal.image_url == "https://ae01.alicdn.com/kf/example.jpg"
    assert len(deal.coupons) == 1
    assert "Save $2" in deal.coupons[0].description


def test_detects_antibot_challenge() -> None:
    html = "<html><title>punish</title><script>var x5sec='captcha';</script></html>"
    with pytest.raises(AntiBotChallengeError):
        extract_init_data_json(html)
