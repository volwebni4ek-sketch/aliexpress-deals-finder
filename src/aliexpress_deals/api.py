from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from aliexpress_deals.config import get_settings
from aliexpress_deals.filters import filter_and_sort_deals
from aliexpress_deals.models import ProductDeal, SearchQuery, SortBy
from aliexpress_deals.monitor import PriceMonitor
from aliexpress_deals.providers import build_provider
from aliexpress_deals.providers.base import AntiBotChallengeError, ProviderError

app = FastAPI(
    title="AliExpress Deals Finder API",
    version="0.1.0",
    description="Search AliExpress deals, calculate total landed cost, and track price drops & promos.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/search", response_model=list[ProductDeal])
async def search_deals(
    keyword: str = Query(..., min_length=1),
    provider: Optional[str] = Query(default=None),
    min_price: Optional[float] = Query(default=None, ge=0),
    max_price: Optional[float] = Query(default=None, ge=0),
    max_total_cost: Optional[float] = Query(default=None, ge=0),
    free_shipping_only: bool = Query(default=False),
    min_discount_pct: Optional[float] = Query(default=None, ge=0, le=100),
    min_rating: Optional[float] = Query(default=None, ge=0, le=5),
    min_orders: Optional[int] = Query(default=None, ge=0),
    has_coupons_only: bool = Query(default=False),
    sort_by: SortBy = Query(default=SortBy.BEST_DEAL),
    ship_to_country: Optional[str] = Query(default=None),
    currency: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ProductDeal]:
    settings = get_settings()
    query = SearchQuery(
        keyword=keyword,
        min_price=min_price,
        max_price=max_price,
        max_total_cost=max_total_cost,
        free_shipping_only=free_shipping_only,
        min_discount_pct=min_discount_pct,
        min_rating=min_rating,
        min_orders=min_orders,
        has_coupons_only=has_coupons_only,
        sort_by=sort_by,
        ship_to_country=ship_to_country or settings.ship_to_country,
        currency=currency or settings.currency,
        limit=limit,
    )

    try:
        active_provider = build_provider(provider or settings.provider, settings)
        raw_deals = await active_provider.search(query)
    except AntiBotChallengeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return filter_and_sort_deals(raw_deals, query)


@app.get("/watchlist")
def get_watchlist() -> list[dict]:
    settings = get_settings()
    monitor = PriceMonitor(settings.db_path)
    return monitor.list_watches()


@app.post("/watchlist")
def add_watchlist_item(keyword: str = Query(..., min_length=1), max_total_cost: Optional[float] = Query(default=None, ge=0)) -> dict:
    settings = get_settings()
    monitor = PriceMonitor(settings.db_path)
    monitor.add_watch(keyword=keyword, max_total_cost=max_total_cost)
    return {"status": "added", "keyword": keyword, "max_total_cost": max_total_cost}
