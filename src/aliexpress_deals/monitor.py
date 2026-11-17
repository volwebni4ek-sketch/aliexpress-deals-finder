from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from aliexpress_deals.models import PriceAlert, ProductDeal


class PriceMonitor:
    """SQLite-backed price, shipping, and promo/coupon history monitor."""

    def __init__(self, db_path: str | Path = "deals.db") -> None:
        self.db_path = str(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS watched_queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL UNIQUE,
                    max_total_cost REAL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS price_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    sale_price REAL NOT NULL,
                    shipping_cost REAL NOT NULL,
                    total_cost REAL NOT NULL,
                    discount_pct REAL NOT NULL,
                    coupons_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_snapshots_product_time
                ON price_snapshots (product_id, recorded_at DESC);

                CREATE TABLE IF NOT EXISTS telegram_promos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel TEXT NOT NULL,
                    code TEXT NOT NULL,
                    description TEXT NOT NULL,
                    discount_amount REAL,
                    min_spend REAL,
                    post_text TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    UNIQUE(channel, code)
                );
                """
            )

    def add_watch(self, keyword: str, max_total_cost: Optional[float] = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO watched_queries (keyword, max_total_cost, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(keyword) DO UPDATE SET max_total_cost = excluded.max_total_cost
                """,
                (keyword.strip(), max_total_cost, now),
            )

    def list_watches(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, keyword, max_total_cost, created_at FROM watched_queries ORDER BY id DESC"
            ).fetchall()
            return [dict(row) for row in rows]

    def record_deals(
        self,
        deals: list[ProductDeal],
        target_max_total_cost: Optional[float] = None,
    ) -> list[PriceAlert]:
        """Persist current snapshots and return any price-drop, target-price, or new-coupon alerts."""
        alerts: list[PriceAlert] = []
        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            for deal in deals:
                prev = conn.execute(
                    """
                    SELECT total_cost, coupons_json
                    FROM price_snapshots
                    WHERE product_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (deal.product_id,),
                ).fetchone()

                current_coupons = [c.description for c in deal.coupons]
                coupons_json = json.dumps(current_coupons, ensure_ascii=False)

                if prev is not None:
                    prev_total = float(prev["total_cost"])
                    prev_coupons = set(json.loads(prev["coupons_json"]))
                    if deal.total_cost < prev_total:
                        drop = round(prev_total - deal.total_cost, 2)
                        alerts.append(
                            PriceAlert(
                                product_id=deal.product_id,
                                title=deal.title,
                                url=deal.url,
                                alert_type="price_drop",
                                previous_total_cost=prev_total,
                                current_total_cost=deal.total_cost,
                                message=f"Price dropped by {drop} {deal.currency} (from {prev_total} to {deal.total_cost})",
                            )
                        )
                    new_coupons = [c for c in current_coupons if c not in prev_coupons]
                    if new_coupons:
                        alerts.append(
                            PriceAlert(
                                product_id=deal.product_id,
                                title=deal.title,
                                url=deal.url,
                                alert_type="new_coupon",
                                previous_total_cost=prev_total,
                                current_total_cost=deal.total_cost,
                                message=f"New promo/coupon detected: {', '.join(new_coupons)}",
                            )
                        )

                if target_max_total_cost is not None and deal.total_cost <= target_max_total_cost:
                    alerts.append(
                        PriceAlert(
                            product_id=deal.product_id,
                            title=deal.title,
                            url=deal.url,
                            alert_type="target_reached",
                            previous_total_cost=float(prev["total_cost"]) if prev else None,
                            current_total_cost=deal.total_cost,
                            message=f"Target price <= {target_max_total_cost} {deal.currency} reached ({deal.total_cost})",
                        )
                    )

                conn.execute(
                    """
                    INSERT INTO price_snapshots (
                        product_id, title, url, sale_price, shipping_cost,
                        total_cost, discount_pct, coupons_json, recorded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        deal.product_id,
                        deal.title,
                        deal.url,
                        deal.sale_price,
                        0.0 if deal.free_shipping else deal.shipping_cost,
                        deal.total_cost,
                        deal.discount_pct,
                        coupons_json,
                        now,
                    ),
                )

        return alerts

    def get_history(self, product_id: str, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT product_id, title, sale_price, shipping_cost, total_cost,
                       discount_pct, coupons_json, recorded_at
                FROM price_snapshots
                WHERE product_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (product_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def save_telegram_promos(self, posts: list) -> int:
        """Persist extracted Telegram promo codes into SQLite and return count saved."""
        now = datetime.now(timezone.utc).isoformat()
        saved = 0
        with self._connect() as conn:
            for post in posts:
                for coupon in post.coupons:
                    code = coupon.code or coupon.description[:32]
                    conn.execute(
                        """
                        INSERT INTO telegram_promos (
                            channel, code, description, discount_amount,
                            min_spend, post_text, recorded_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(channel, code) DO UPDATE SET
                            description = excluded.description,
                            discount_amount = excluded.discount_amount,
                            min_spend = excluded.min_spend,
                            post_text = excluded.post_text,
                            recorded_at = excluded.recorded_at
                        """,
                        (
                            post.channel,
                            code,
                            coupon.description,
                            coupon.discount_amount,
                            coupon.min_spend,
                            post.text,
                            now,
                        ),
                    )
                    saved += 1
        return saved

    def list_telegram_promos(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT channel, code, description, discount_amount, min_spend, post_text, recorded_at
                FROM telegram_promos
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
