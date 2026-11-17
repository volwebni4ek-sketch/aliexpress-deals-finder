from __future__ import annotations

from typing import Any

import httpx

from aliexpress_deals.models import Coupon, ProductDeal, SearchQuery
from aliexpress_deals.providers.base import ProviderError


class RapidApiScraperProvider:
    """Optional provider using RapidAPI AliExpress Scraper endpoints."""

    name = "rapidapi"

    def __init__(self, api_key: str, host: str = "aliexpress-scraper-api1.p.rapidapi.com") -> None:
        if not api_key:
            raise ProviderError("AE_RAPIDAPI_KEY is required when using the 'rapidapi' provider.")
        self.api_key = api_key
        self.host = host

    async def search(self, query: SearchQuery) -> list[ProductDeal]:
        headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": self.host,
        }
        params: dict[str, Any] = {
            "query": query.keyword,
            "page": query.page,
            "country_code": query.ship_to_country,
        }
        if query.min_price is not None:
            params["min_price"] = query.min_price
        if query.max_price is not None:
            params["max_price"] = query.max_price

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(f"https://{self.host}/search", headers=headers, params=params)
            if resp.status_code >= 400:
                raise ProviderError(f"RapidAPI error {resp.status_code}: {resp.text[:200]}")
            data = resp.json()

        items = data.get("results") or data.get("items") or []
        deals: list[ProductDeal] = []
        for item in items:
            pid = str(item.get("product_id") or item.get("id") or "")
            if not pid:
                continue
            sale_price = float(item.get("sale_price") or item.get("price") or 0)
            orig_price = item.get("original_price")
            ship = float(item.get("shipping_cost") or 0)
            coupons = [
                Coupon(description=str(c)) for c in (item.get("coupons") or [])
            ]
            deals.append(
                ProductDeal(
                    product_id=pid,
                    title=str(item.get("title") or "Untitled"),
                    url=str(item.get("url") or f"https://www.aliexpress.com/item/{pid}.html"),
                    image_url=item.get("image_url"),
                    sale_price=sale_price,
                    original_price=float(orig_price) if orig_price is not None else None,
                    shipping_cost=ship,
                    currency=str(item.get("currency") or query.currency),
                    rating=float(item["rating"]) if item.get("rating") is not None else None,
                    orders_count=int(item.get("orders") or 0),
                    store_name=item.get("store_name"),
                    free_shipping=(ship == 0),
                    coupons=coupons,
                )
            )
        return deals
