from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from aliexpress_deals.models import Coupon, ProductDeal


class CustomsMode(str, Enum):
    STANDARD_150EUR = "standard_150eur"   # 10% duty + 20% VAT (32% effective) above 150 EUR
    ENERGY_EXEMPT = "energy_exempt"       # 0% duty/VAT for eligible energy equipment (power stations, LiFePO4)
    NONE = "none"


class ForwarderRate(BaseModel):
    country_code: str
    provider_name: str
    base_fee_usd: float = 3.0
    per_kg_usd: float = 3.5


DEFAULT_FORWARDERS: dict[str, ForwarderRate] = {
    "PL": ForwarderRate(country_code="PL", provider_name="Meest Poland / NP Shopping PL", base_fee_usd=2.5, per_kg_usd=3.0),
    "DE": ForwarderRate(country_code="DE", provider_name="Meest Germany / NP Shopping DE", base_fee_usd=3.5, per_kg_usd=3.8),
    "CZ": ForwarderRate(country_code="CZ", provider_name="NP Shopping CZ", base_fee_usd=3.0, per_kg_usd=3.5),
    "FR": ForwarderRate(country_code="FR", provider_name="NP Shopping FR / Meest FR", base_fee_usd=4.0, per_kg_usd=4.5),
    "NL": ForwarderRate(country_code="NL", provider_name="Meest / EU Forwarder NL", base_fee_usd=4.0, per_kg_usd=4.5),
    "ES": ForwarderRate(country_code="ES", provider_name="NP Shopping ES / Meest ES", base_fee_usd=4.0, per_kg_usd=4.5),
    "IT": ForwarderRate(country_code="IT", provider_name="NP Shopping IT / Meest IT", base_fee_usd=4.0, per_kg_usd=4.5),
    "GB": ForwarderRate(country_code="GB", provider_name="NP Shopping UK / Meest UK", base_fee_usd=4.5, per_kg_usd=5.0),
    "US": ForwarderRate(country_code="US", provider_name="NP Shopping US / Meest US", base_fee_usd=5.0, per_kg_usd=6.5),
}


class LandedCostBreakdown(BaseModel):
    route_country: str
    warehouse_country: Optional[str] = None
    sale_price_usd: float
    applied_coupon_code: Optional[str] = None
    coupon_discount_usd: float = 0.0
    ali_shipping_usd: float = 0.0
    forwarder_shipping_usd: float = 0.0
    customs_tax_usd: float = 0.0
    final_landed_cost_usd: float
    notes: str = ""


def match_best_coupon(sale_price: float, coupons: list[Coupon]) -> Optional[Coupon]:
    """Pick the coupon offering the largest discount whose min_spend <= sale_price."""
    best: Optional[Coupon] = None
    best_discount = 0.0
    for c in coupons:
        if c.discount_amount is None or c.discount_amount <= 0:
            continue
        min_spend = c.min_spend or 0.0
        if sale_price >= min_spend and c.discount_amount > best_discount:
            best = c
            best_discount = c.discount_amount
    return best


def calculate_ua_customs_usd(
    net_item_price_usd: float,
    customs_mode: CustomsMode = CustomsMode.STANDARD_150EUR,
    eur_to_usd_rate: float = 1.08,
) -> float:
    """Calculate Ukrainian import customs + VAT on the portion exceeding 150 EUR."""
    if customs_mode in (CustomsMode.ENERGY_EXEMPT, CustomsMode.NONE):
        return 0.0
    threshold_usd = 150.0 * eur_to_usd_rate  # ~162 USD
    if net_item_price_usd <= threshold_usd:
        return 0.0
    excess = net_item_price_usd - threshold_usd
    duty = excess * 0.10
    vat = (excess + duty) * 0.20
    return round(duty + vat, 2)


def estimate_landed_cost(
    deal: ProductDeal,
    route_country: str = "UA",
    estimated_weight_kg: float = 0.5,
    customs_mode: CustomsMode = CustomsMode.STANDARD_150EUR,
    extra_coupons: Optional[list[Coupon]] = None,
    eur_to_usd_rate: float = 1.08,
) -> LandedCostBreakdown:
    """Compute final landed cost in Ukraine for direct UA shipping or via EU forwarder (PL/DE/CZ)."""
    all_coupons = list(deal.coupons) + (extra_coupons or [])
    best_coupon = match_best_coupon(deal.sale_price, all_coupons)
    coupon_discount = best_coupon.discount_amount if (best_coupon and best_coupon.discount_amount) else 0.0
    net_price = max(0.0, round(deal.sale_price - coupon_discount, 2))

    ali_ship = 0.0 if deal.free_shipping else deal.shipping_cost
    route = route_country.upper()

    if route == "UA":
        forwarder_fee = 0.0
        notes = "Direct shipping to Ukraine"
    else:
        fw = DEFAULT_FORWARDERS.get(
            route,
            ForwarderRate(country_code=route, provider_name=f"Forwarder ({route})", base_fee_usd=4.0, per_kg_usd=4.0),
        )
        forwarder_fee = round(fw.base_fee_usd + fw.per_kg_usd * max(estimated_weight_kg, 0.1), 2)
        notes = f"Via {fw.provider_name} ({estimated_weight_kg:.1f} kg)"

    customs_usd = calculate_ua_customs_usd(
        net_item_price_usd=net_price,
        customs_mode=customs_mode,
        eur_to_usd_rate=eur_to_usd_rate,
    )
    final_cost = round(net_price + ali_ship + forwarder_fee + customs_usd, 2)

    return LandedCostBreakdown(
        route_country=route,
        sale_price_usd=deal.sale_price,
        applied_coupon_code=best_coupon.code or best_coupon.description if best_coupon else None,
        coupon_discount_usd=coupon_discount,
        ali_shipping_usd=ali_ship,
        forwarder_shipping_usd=forwarder_fee,
        customs_tax_usd=customs_usd,
        final_landed_cost_usd=final_cost,
        notes=notes,
    )
