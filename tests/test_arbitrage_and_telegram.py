from pathlib import Path

from aliexpress_deals.arbitrage import CustomsMode, estimate_landed_cost
from aliexpress_deals.exporter import export_deals_to_csv
from aliexpress_deals.models import Coupon, ProductDeal
from aliexpress_deals.presets import EQUIPMENT_PRESETS
from aliexpress_deals.telegram_promos import parse_telegram_channel_html


def test_power_station_eu_arbitrage_vs_direct() -> None:
    # A 2048Wh power station from Poland warehouse with free EU shipping and $50 coupon
    deal_pl = ProductDeal(
        product_id="100500777",
        title="Fossibot F2400 2048Wh 2400W LiFePO4 Power Station",
        url="https://www.aliexpress.com/item/100500777.html",
        sale_price=699.0,
        original_price=999.0,
        shipping_cost=0.0,
        free_shipping=True,
        coupons=[Coupon(code="EU50", description="$50 off $500", discount_amount=50.0, min_spend=500.0)],
    )
    breakdown_exempt = estimate_landed_cost(
        deal_pl,
        route_country="PL",
        estimated_weight_kg=22.0,
        customs_mode=CustomsMode.ENERGY_EXEMPT,
    )
    # 699 - 50 = 649 net; forwarder PL = 2.5 + 3.0 * 22 = 68.5; customs = 0 -> 717.50
    assert breakdown_exempt.coupon_discount_usd == 50.0
    assert breakdown_exempt.customs_tax_usd == 0.0
    assert breakdown_exempt.forwarder_shipping_usd == 68.5
    assert breakdown_exempt.final_landed_cost_usd == 717.5

    breakdown_std = estimate_landed_cost(
        deal_pl,
        route_country="PL",
        estimated_weight_kg=22.0,
        customs_mode=CustomsMode.STANDARD_150EUR,
    )
    assert breakdown_std.customs_tax_usd > 100.0
    assert breakdown_std.final_landed_cost_usd > breakdown_exempt.final_landed_cost_usd


def test_telegram_channel_promo_extraction() -> None:
    sample_html = """
    <div class="tgme_widget_message_text js-message_text" dir="auto">
      🔥 Гаряча знижка на паяльник FNIRSI HS-02!<br/>
      Промокод: <b>AEUA12</b> дає 12$ від 80$<br/>
      Купити тут: https://s.click.aliexpress.com/e/_dc12345
    </div>
    """
    posts = parse_telegram_channel_html(sample_html, channel="ali_ua_deals")
    assert len(posts) == 1
    post = posts[0]
    assert post.links == ["https://s.click.aliexpress.com/e/_dc12345"]
    assert len(post.coupons) == 1
    assert post.coupons[0].code == "AEUA12"
    assert post.coupons[0].discount_amount == 12.0
    assert post.coupons[0].min_spend == 80.0


def test_presets_and_csv_export(tmp_path: Path) -> None:
    assert "power_station_2kwh" in EQUIPMENT_PRESETS
    assert "hydraulic_crimper" in EQUIPMENT_PRESETS
    assert "multimeter" in EQUIPMENT_PRESETS

    csv_file = tmp_path / "deals.csv"
    deals = [
        ProductDeal(
            product_id="9001",
            title="YQK-70 Hydraulic Crimper",
            url="https://www.aliexpress.com/item/9001.html",
            sale_price=24.5,
            shipping_cost=0.0,
            free_shipping=True,
        )
    ]
    export_deals_to_csv(deals, csv_file)
    content = csv_file.read_text(encoding="utf-8")
    assert "YQK-70 Hydraulic Crimper" in content
    assert "24.5" in content
