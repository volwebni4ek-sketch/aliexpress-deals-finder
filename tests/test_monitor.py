from pathlib import Path

from aliexpress_deals.models import Coupon, ProductDeal
from aliexpress_deals.monitor import PriceMonitor


def test_price_drop_and_new_coupon_alerts(tmp_path: Path) -> None:
    db_file = tmp_path / "test_deals.db"
    monitor = PriceMonitor(db_file)

    first = [
        ProductDeal(
            product_id="555",
            title="NVMe Enclosure",
            url="https://www.aliexpress.com/item/555.html",
            sale_price=22.0,
            shipping_cost=3.0,
            coupons=[],
        )
    ]
    alerts_1 = monitor.record_deals(first, target_max_total_cost=20.0)
    assert alerts_1 == []

    second = [
        ProductDeal(
            product_id="555",
            title="NVMe Enclosure",
            url="https://www.aliexpress.com/item/555.html",
            sale_price=18.0,
            shipping_cost=0.0,
            free_shipping=True,
            coupons=[Coupon(description="$2 off")],
        )
    ]
    alerts_2 = monitor.record_deals(second, target_max_total_cost=20.0)
    alert_types = {a.alert_type for a in alerts_2}
    assert alert_types == {"price_drop", "new_coupon", "target_reached"}
    assert len(monitor.get_history("555")) == 2
