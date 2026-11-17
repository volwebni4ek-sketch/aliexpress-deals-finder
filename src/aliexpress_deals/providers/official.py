from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any

import httpx

from aliexpress_deals.models import ProductDeal, SearchQuery
from aliexpress_deals.providers.base import ProviderError


class OfficialOpenPlatformProvider:
    """Adapter for the official AliExpress Open Platform Affiliate API."""

    name = "official"
    ENDPOINT = "https://api-sg.aliexpress.com/sync"

    def __init__(self, app_key: str, app_secret: str, tracking_id: str = "default") -> None:
        if not app_key or not app_secret:
            raise ProviderError("AE_APP_KEY and AE_APP_SECRET are required for the 'official' provider.")
        self.app_key = app_key
        self.app_secret = app_secret
        self.tracking_id = tracking_id

    def _sign(self, params: dict[str, Any]) -> str:
        sorted_items = sorted((k, str(v)) for k, v in params.items() if k != "sign")
        joined = "".join(f"{k}{v}" for k, v in sorted_items)
        return hmac.new(
            self.app_secret.encode("utf-8"),
            joined.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest().upper()

    async def search(self, query: SearchQuery) -> list[ProductDeal]:
        params: dict[str, Any] = {
            "app_key": self.app_key,
            "method": "aliexpress.affiliate.product.query",
            "timestamp": str(int(time.time() * 1000)),
            "sign_method": "sha256",
            "keywords": query.keyword,
            "page_no": query.page,
            "page_size": min(query.limit, 50),
            "target_currency": query.currency,
            "ship_to_country": query.ship_to_country,
            "tracking_id": self.tracking_id,
        }
        if query.min_price is not None:
            params["min_sale_price"] = int(query.min_price * 100)
        if query.max_price is not None:
            params["max_sale_price"] = int(query.max_price * 100)

        params["sign"] = self._sign(params)

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(self.ENDPOINT, data=params)
            resp.raise_for_status()
            data = resp.json()

        result = (
            data.get("aliexpress_affiliate_product_query_response", {})
            .get("resp_result", {})
            .get("result", {})
        )
        products = result.get("products", {}).get("product", [])
        deals: list[ProductDeal] = []
        for p in products:
            pid = str(p.get("product_id") or "")
            if not pid:
                continue
            sale = float(p.get("target_sale_price") or p.get("sale_price") or 0)
            orig = p.get("target_original_price") or p.get("original_price")
            deals.append(
                ProductDeal(
                    product_id=pid,
                    title=str(p.get("product_title") or ""),
                    url=str(p.get("promotion_link") or p.get("product_detail_url") or f"https://www.aliexpress.com/item/{pid}.html"),
                    image_url=p.get("product_main_image_url"),
                    sale_price=sale,
                    original_price=float(orig) if orig is not None else None,
                    shipping_cost=0.0,
                    currency=query.currency,
                    rating=float(p["evaluate_rate"].rstrip("%")) / 20.0 if p.get("evaluate_rate") else None,
                    orders_count=int(p.get("lastest_volume") or 0),
                    store_name=p.get("shop_url"),
                    free_shipping=False,
                )
            )
        return deals
