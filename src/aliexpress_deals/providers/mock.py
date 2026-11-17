from __future__ import annotations

from aliexpress_deals.models import Coupon, ProductDeal, SearchQuery


class MockProvider:
    """Offline mock provider for local demos and automated tests."""

    name = "mock"

    async def search(self, query: SearchQuery) -> list[ProductDeal]:
        kw = query.keyword.strip()
        sample_items = [
            ProductDeal(
                product_id="10050061234501",
                title=f"{kw.title()} Pro Wireless Edition (Hot Deal)",
                url="https://www.aliexpress.com/item/10050061234501.html",
                sale_price=34.99,
                original_price=69.99,
                shipping_cost=0.0,
                free_shipping=True,
                currency=query.currency,
                rating=4.9,
                orders_count=2450,
                store_name="TechDirect Official Store",
                coupons=[Coupon(code="SAVE5", description="$5 off orders over $30", discount_amount=5.0, min_spend=30.0)],
                promo_badges=["Choice", "SuperDeals"],
            ),
            ProductDeal(
                product_id="10050061234502",
                title=f"Budget {kw.title()} Mini Compact",
                url="https://www.aliexpress.com/item/10050061234502.html",
                sale_price=19.50,
                original_price=25.00,
                shipping_cost=12.90,
                free_shipping=False,
                currency=query.currency,
                rating=4.3,
                orders_count=180,
                store_name="Shenzhen Value Hub",
                coupons=[],
                promo_badges=[],
            ),
            ProductDeal(
                product_id="10050061234503",
                title=f"Ultra {kw.title()} RGB Aluminum",
                url="https://www.aliexpress.com/item/10050061234503.html",
                sale_price=48.00,
                original_price=80.00,
                shipping_cost=0.0,
                free_shipping=True,
                currency=query.currency,
                rating=4.8,
                orders_count=920,
                store_name="KeyMaster Flagship",
                coupons=[Coupon(code="DEAL8", description="$8 off store coupon", discount_amount=8.0, min_spend=45.0)],
                promo_badges=["Choice"],
            ),
            ProductDeal(
                product_id="10050061234504",
                title=f"{kw.title()} Starter Kit",
                url="https://www.aliexpress.com/item/10050061234504.html",
                sale_price=14.99,
                original_price=16.00,
                shipping_cost=3.50,
                free_shipping=False,
                currency=query.currency,
                rating=4.1,
                orders_count=45,
                store_name="Global Gadgets",
                coupons=[],
                promo_badges=["Welcome Deal"],
            ),
        ]
        return sample_items
