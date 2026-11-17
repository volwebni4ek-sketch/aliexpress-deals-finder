from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Optional

import httpx

from aliexpress_deals.models import Coupon, ProductDeal, SearchQuery, SortBy
from aliexpress_deals.providers.base import AntiBotChallengeError, ProviderError

_PRICE_RE = re.compile(r"([\d]+(?:[.,]\d+)?)")
_ORDERS_RE = re.compile(r"([\d,]+)\+?\s*(?:sold|orders?)?", re.IGNORECASE)

_SORT_MAP = {
    SortBy.BEST_DEAL: "default",
    SortBy.TOTAL_PRICE_ASC: "price_asc",
    SortBy.TOTAL_PRICE_DESC: "price_desc",
    SortBy.ORDERS_DESC: "total_tranpro_desc",
    SortBy.DISCOUNT_DESC: "default",
    SortBy.RATING_DESC: "default",
}


def _parse_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").strip()
    match = _PRICE_RE.search(text)
    return float(match.group(1)) if match else None


def _parse_orders(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    match = _ORDERS_RE.search(str(value))
    if not match:
        return 0
    return int(match.group(1).replace(",", ""))


def extract_init_data_json(html: str) -> dict[str, Any]:
    """Extract embedded search JSON (_init_data_ or DCData) from AliExpress search HTML."""
    lower = html.lower()
    if "punish" in lower and ("captcha" in lower or "x5sec" in lower or "_____tmd_____" in lower):
        raise AntiBotChallengeError(
            "AliExpress returned an anti-bot/CAPTCHA challenge page. "
            "Reduce request frequency, verify network/exit IP, or use an API provider."
        )

    markers = [
        "_init_data_=",
        "window._d_c_.DCData=",
        "window.runParams=",
    ]
    decoder = json.JSONDecoder()

    for marker in markers:
        idx = html.find(marker)
        if idx == -1:
            continue
        start = html.find("{", idx + len(marker))
        if start == -1:
            continue
        try:
            obj, _ = decoder.raw_decode(html, start)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue

    raise ProviderError("Could not locate embedded product JSON in AliExpress search response.")


def _find_item_list(data: Any) -> list[dict[str, Any]]:
    """Recursively locate the itemList array inside AliExpress's nested JSON payload."""
    if isinstance(data, dict):
        if "itemList" in data and isinstance(data["itemList"], dict):
            content = data["itemList"].get("content")
            if isinstance(content, list):
                return [item for item in content if isinstance(item, dict)]
        if "mods" in data and isinstance(data["mods"], dict):
            item_list = data["mods"].get("itemList")
            if isinstance(item_list, dict) and isinstance(item_list.get("content"), list):
                return [item for item in item_list["content"] if isinstance(item, dict)]
        for value in data.values():
            found = _find_item_list(value)
            if found:
                return found
    elif isinstance(data, list):
        for entry in data:
            found = _find_item_list(entry)
            if found:
                return found
    return []


def parse_search_items(payload: dict[str, Any], currency: str = "USD") -> list[ProductDeal]:
    """Convert raw AliExpress search JSON payload into normalized ProductDeal models."""
    raw_items = _find_item_list(payload)
    deals: list[ProductDeal] = []

    for item in raw_items:
        product_id = str(item.get("productId") or item.get("itemId") or "").strip()
        if not product_id:
            continue

        title_obj = item.get("title") or {}
        if isinstance(title_obj, dict):
            title = str(title_obj.get("displayTitle") or title_obj.get("seoTitle") or "").strip()
        else:
            title = str(title_obj).strip()
        if not title:
            continue

        prices = item.get("prices") or {}
        sale_obj = prices.get("salePrice") or {}
        orig_obj = prices.get("originalPrice") or {}

        sale_price = _parse_float(
            sale_obj.get("minPrice") or sale_obj.get("formattedPrice") or item.get("salePrice")
        )
        if sale_price is None:
            continue

        original_price = _parse_float(
            orig_obj.get("minPrice") or orig_obj.get("formattedPrice") or item.get("originalPrice")
        )

        # Shipping & promo badges
        shipping_cost = 0.0
        free_shipping = False
        promo_badges: list[str] = []
        coupons: list[Coupon] = []

        selling_points = item.get("sellingPoints") or []
        for sp in selling_points:
            if not isinstance(sp, dict):
                continue
            tag_text = str(sp.get("tagContent", {}).get("tagText") or sp.get("text") or "").strip()
            if not tag_text:
                continue
            lower_tag = tag_text.lower()
            if "free shipping" in lower_tag or "free delivery" in lower_tag:
                free_shipping = True
                shipping_cost = 0.0
            elif "shipping" in lower_tag or "delivery" in lower_tag:
                parsed_ship = _parse_float(tag_text)
                if parsed_ship is not None:
                    shipping_cost = parsed_ship
            elif "off" in lower_tag or "coupon" in lower_tag or "save" in lower_tag or "promo" in lower_tag:
                coupons.append(Coupon(description=tag_text))
            else:
                promo_badges.append(tag_text)

        # Explicit shipping field fallback
        logistics = item.get("logisticsDesc") or item.get("shippingFee")
        if logistics and not free_shipping:
            if "free" in str(logistics).lower():
                free_shipping = True
                shipping_cost = 0.0
            else:
                parsed_ship = _parse_float(logistics)
                if parsed_ship is not None:
                    shipping_cost = parsed_ship

        evaluation = item.get("evaluation") or {}
        rating = _parse_float(evaluation.get("starRating") or item.get("starRating"))
        if rating is not None and rating > 5.0:
            rating = 5.0

        trade = item.get("trade") or {}
        orders_count = _parse_orders(trade.get("tradeDesc") or item.get("orders"))

        store = item.get("store") or {}
        store_name = store.get("storeName")

        image_obj = item.get("image") or {}
        img_url = image_obj.get("imgUrl")
        if isinstance(img_url, str) and img_url.startswith("//"):
            img_url = f"https:{img_url}"

        deals.append(
            ProductDeal(
                product_id=product_id,
                title=title,
                url=f"https://www.aliexpress.com/item/{product_id}.html",
                image_url=img_url,
                sale_price=sale_price,
                original_price=original_price,
                shipping_cost=shipping_cost,
                currency=str(sale_obj.get("currencyCode") or currency),
                rating=rating,
                orders_count=orders_count,
                store_name=store_name,
                free_shipping=free_shipping,
                coupons=coupons,
                promo_badges=promo_badges,
            )
        )

    return deals


class DirectWebSearchProvider:
    """Scrapes AliExpress public search HTML/JSON without requiring API keys."""

    name = "web"

    def __init__(self, timeout: float = 20.0, max_retries: int = 2) -> None:
        self.timeout = timeout
        self.max_retries = max_retries

    async def search(self, query: SearchQuery) -> list[ProductDeal]:
        params: dict[str, Any] = {
            "SearchText": query.keyword,
            "page": query.page,
            "SortType": _SORT_MAP.get(query.sort_by, "default"),
        }
        if query.min_price is not None:
            params["minPrice"] = query.min_price
        if query.max_price is not None:
            params["maxPrice"] = query.max_price
        if query.free_shipping_only:
            params["isFreeShip"] = "y"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        cookies = {
            "aep_usuc_f": f"site=glo&c_tp={query.currency}&region={query.ship_to_country}&b_locale=en_US",
        }

        last_err: Optional[Exception] = None
        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers=headers,
            cookies=cookies,
        ) as client:
            for attempt in range(self.max_retries + 1):
                try:
                    resp = await client.get("https://www.aliexpress.com/wholesale", params=params)
                    if resp.status_code in (403, 429):
                        if attempt < self.max_retries:
                            await asyncio.sleep(2.0 * (attempt + 1))
                            continue
                        raise ProviderError(f"AliExpress returned HTTP {resp.status_code} (rate limited/blocked).")
                    resp.raise_for_status()
                    payload = extract_init_data_json(resp.text)
                    return parse_search_items(payload, currency=query.currency)
                except AntiBotChallengeError:
                    raise
                except httpx.HTTPError as exc:
                    last_err = exc
                    if attempt < self.max_retries:
                        await asyncio.sleep(1.5 * (attempt + 1))
                        continue
                    raise ProviderError(f"HTTP error querying AliExpress: {exc}") from exc

        raise ProviderError(f"Failed to fetch AliExpress search results: {last_err}")
