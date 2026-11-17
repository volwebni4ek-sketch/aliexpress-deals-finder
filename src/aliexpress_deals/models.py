from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class SortBy(str, Enum):
    BEST_DEAL = "best_deal"
    TOTAL_PRICE_ASC = "total_price_asc"
    TOTAL_PRICE_DESC = "total_price_desc"
    DISCOUNT_DESC = "discount_desc"
    ORDERS_DESC = "orders_desc"
    RATING_DESC = "rating_desc"


class Coupon(BaseModel):
    code: Optional[str] = None
    description: str
    discount_amount: Optional[float] = None
    min_spend: Optional[float] = None


class ProductDeal(BaseModel):
    product_id: str
    title: str
    url: str
    image_url: Optional[str] = None
    sale_price: float = Field(ge=0)
    original_price: Optional[float] = Field(default=None, ge=0)
    shipping_cost: float = Field(default=0.0, ge=0)
    currency: str = "USD"
    rating: Optional[float] = Field(default=None, ge=0, le=5)
    orders_count: int = Field(default=0, ge=0)
    store_name: Optional[str] = None
    free_shipping: bool = False
    coupons: list[Coupon] = Field(default_factory=list)
    promo_badges: list[str] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @computed_field
    @property
    def total_cost(self) -> float:
        return round(self.sale_price + (0.0 if self.free_shipping else self.shipping_cost), 2)

    @computed_field
    @property
    def discount_pct(self) -> float:
        if not self.original_price or self.original_price <= self.sale_price:
            return 0.0
        return round(((self.original_price - self.sale_price) / self.original_price) * 100, 1)

    @computed_field
    @property
    def deal_score(self) -> float:
        """Composite score (0..100) balancing discount, rating, orders, and shipping."""
        discount_component = min(self.discount_pct, 70.0) * 0.55  # up to 38.5
        rating_component = ((self.rating or 4.0) / 5.0) * 25.0     # up to 25.0
        # Logarithmic-like orders boost capped at 20 points
        orders = max(self.orders_count, 0)
        if orders >= 1000:
            orders_component = 20.0
        elif orders >= 200:
            orders_component = 15.0
        elif orders >= 50:
            orders_component = 10.0
        elif orders >= 10:
            orders_component = 5.0
        else:
            orders_component = 1.0

        shipping_bonus = 10.0 if (self.free_shipping or self.shipping_cost == 0) else max(
            0.0, 10.0 - (self.shipping_cost / max(self.sale_price, 1.0)) * 20.0
        )
        promo_bonus = min(len(self.coupons) * 3.5 + len(self.promo_badges) * 1.5, 6.5)
        return round(
            min(100.0, discount_component + rating_component + orders_component + shipping_bonus + promo_bonus),
            1,
        )


class SearchQuery(BaseModel):
    keyword: str = Field(min_length=1)
    min_price: Optional[float] = Field(default=None, ge=0)
    max_price: Optional[float] = Field(default=None, ge=0)
    max_total_cost: Optional[float] = Field(default=None, ge=0)
    free_shipping_only: bool = False
    min_discount_pct: Optional[float] = Field(default=None, ge=0, le=100)
    min_rating: Optional[float] = Field(default=None, ge=0, le=5)
    min_orders: Optional[int] = Field(default=None, ge=0)
    has_coupons_only: bool = False
    sort_by: SortBy = SortBy.BEST_DEAL
    ship_to_country: str = "UA"
    currency: str = "USD"
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class PriceAlert(BaseModel):
    product_id: str
    title: str
    url: str
    alert_type: str  # "price_drop" | "target_reached" | "new_coupon"
    previous_total_cost: Optional[float] = None
    current_total_cost: float
    message: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
