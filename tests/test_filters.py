from aliexpress_deals.filters import filter_and_sort_deals
from aliexpress_deals.models import Coupon, ProductDeal, SearchQuery, SortBy


def _sample_deals() -> list[ProductDeal]:
    return [
        ProductDeal(
            product_id="1",
            title="High Discount Free Ship",
            url="https://www.aliexpress.com/item/1.html",
            sale_price=20.0,
            original_price=50.0,
            shipping_cost=0.0,
            free_shipping=True,
            rating=4.9,
            orders_count=1200,
            coupons=[Coupon(description="$3 off")],
        ),
        ProductDeal(
            product_id="2",
            title="Cheap Item Expensive Ship",
            url="https://www.aliexpress.com/item/2.html",
            sale_price=10.0,
            original_price=12.0,
            shipping_cost=18.0,
            free_shipping=False,
            rating=4.2,
            orders_count=30,
        ),
        ProductDeal(
            product_id="3",
            title="Mid Price Good Rating",
            url="https://www.aliexpress.com/item/3.html",
            sale_price=25.0,
            original_price=40.0,
            shipping_cost=2.0,
            free_shipping=False,
            rating=4.7,
            orders_count=300,
        ),
    ]


def test_total_cost_and_max_total_cost_filter() -> None:
    query = SearchQuery(keyword="ssd", max_total_cost=25.0, sort_by=SortBy.TOTAL_PRICE_ASC)
    results = filter_and_sort_deals(_sample_deals(), query)
    assert [d.product_id for d in results] == ["1"]
    assert results[0].total_cost == 20.0
    assert results[0].discount_pct == 60.0


def test_free_shipping_and_coupons_filter() -> None:
    query = SearchQuery(keyword="ssd", free_shipping_only=True, has_coupons_only=True)
    results = filter_and_sort_deals(_sample_deals(), query)
    assert len(results) == 1
    assert results[0].product_id == "1"


def test_best_deal_ranking_prefers_high_score() -> None:
    query = SearchQuery(keyword="ssd", sort_by=SortBy.BEST_DEAL)
    results = filter_and_sort_deals(_sample_deals(), query)
    assert results[0].product_id == "1"
    assert results[-1].product_id == "2"
