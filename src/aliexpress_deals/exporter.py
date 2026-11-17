from __future__ import annotations

import csv
import json
from pathlib import Path

from aliexpress_deals.models import ProductDeal


def export_deals_to_csv(deals: list[ProductDeal], path: str | Path) -> Path:
    target = Path(path)
    fieldnames = [
        "product_id",
        "deal_score",
        "title",
        "sale_price",
        "shipping_cost",
        "total_cost",
        "original_price",
        "discount_pct",
        "currency",
        "free_shipping",
        "rating",
        "orders_count",
        "store_name",
        "coupons",
        "promo_badges",
        "url",
    ]
    with target.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for d in deals:
            writer.writerow(
                {
                    "product_id": d.product_id,
                    "deal_score": d.deal_score,
                    "title": d.title,
                    "sale_price": d.sale_price,
                    "shipping_cost": 0.0 if d.free_shipping else d.shipping_cost,
                    "total_cost": d.total_cost,
                    "original_price": d.original_price or "",
                    "discount_pct": d.discount_pct,
                    "currency": d.currency,
                    "free_shipping": d.free_shipping,
                    "rating": d.rating or "",
                    "orders_count": d.orders_count,
                    "store_name": d.store_name or "",
                    "coupons": "; ".join(c.description for c in d.coupons),
                    "promo_badges": "; ".join(d.promo_badges),
                    "url": d.url,
                }
            )
    return target


def export_deals_to_json(deals: list[ProductDeal], path: str | Path) -> Path:
    target = Path(path)
    payload = [d.model_dump(mode="json") for d in deals]
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return target
