from __future__ import annotations

from aliexpress_deals.models import ProductDeal, SearchQuery, SortBy


def filter_and_sort_deals(deals: list[ProductDeal], query: SearchQuery) -> list[ProductDeal]:
    """Apply user-specified price, shipping, discount, rating, and coupon filters."""
    filtered: list[ProductDeal] = []

    for deal in deals:
        if query.min_price is not None and deal.sale_price < query.min_price:
            continue
        if query.max_price is not None and deal.sale_price > query.max_price:
            continue
        if query.max_total_cost is not None and deal.total_cost > query.max_total_cost:
            continue
        if query.free_shipping_only and not (deal.free_shipping or deal.shipping_cost == 0):
            continue
        if query.min_discount_pct is not None and deal.discount_pct < query.min_discount_pct:
            continue
        if query.min_rating is not None and (deal.rating is None or deal.rating < query.min_rating):
            continue
        if query.min_orders is not None and deal.orders_count < query.min_orders:
            continue
        if query.has_coupons_only and not (deal.coupons or deal.promo_badges):
            continue
        filtered.append(deal)

    sort_key_map = {
        SortBy.BEST_DEAL: (lambda d: (-d.deal_score, d.total_cost)),
        SortBy.TOTAL_PRICE_ASC: (lambda d: (d.total_cost, -d.deal_score)),
        SortBy.TOTAL_PRICE_DESC: (lambda d: (-d.total_cost, -d.deal_score)),
        SortBy.DISCOUNT_DESC: (lambda d: (-d.discount_pct, d.total_cost)),
        SortBy.ORDERS_DESC: (lambda d: (-d.orders_count, d.total_cost)),
        SortBy.RATING_DESC: (lambda d: (-(d.rating or 0.0), -d.orders_count)),
    }

    filtered.sort(key=sort_key_map[query.sort_by])
    return filtered[: query.limit]
