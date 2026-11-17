from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Optional

from rich.console import Console
from rich.table import Table

from aliexpress_deals.config import get_settings
from aliexpress_deals.filters import filter_and_sort_deals
from aliexpress_deals.models import SearchQuery, SortBy
from aliexpress_deals.monitor import PriceMonitor
from aliexpress_deals.providers import build_provider
from aliexpress_deals.providers.base import ProviderError

console = Console()


def _render_deals_table(deals, keyword: str) -> None:
    table = Table(title=f"AliExpress Deals for '{keyword}' ({len(deals)} found)")
    table.add_column("Score", justify="right", style="cyan")
    table.add_column("Title", max_width=42)
    table.add_column("Price", justify="right", style="green")
    table.add_column("Ship", justify="right")
    table.add_column("Total", justify="right", style="bold yellow")
    table.add_column("Disc%", justify="right", style="magenta")
    table.add_column("Rating", justify="right")
    table.add_column("Orders", justify="right")
    table.add_column("Promos / Coupons", max_width=28)

    for d in deals:
        ship_str = "FREE" if (d.free_shipping or d.shipping_cost == 0) else f"{d.shipping_cost:.2f}"
        promos = [c.description for c in d.coupons] + d.promo_badges
        table.add_row(
            f"{d.deal_score:.1f}",
            d.title,
            f"{d.sale_price:.2f} {d.currency}",
            ship_str,
            f"{d.total_cost:.2f}",
            f"-{d.discount_pct:.0f}%" if d.discount_pct else "-",
            f"{d.rating:.1f}" if d.rating else "-",
            str(d.orders_count),
            ", ".join(promos) if promos else "-",
        )
    console.print(table)


async def _run_search(args: argparse.Namespace) -> int:
    settings = get_settings()
    provider_name = args.provider or settings.provider
    provider = build_provider(provider_name, settings)

    query = SearchQuery(
        keyword=args.keyword,
        min_price=args.min_price,
        max_price=args.max_price,
        max_total_cost=args.max_total_cost,
        free_shipping_only=args.free_shipping,
        min_discount_pct=args.min_discount,
        min_rating=args.min_rating,
        min_orders=args.min_orders,
        has_coupons_only=args.coupons_only,
        sort_by=SortBy(args.sort),
        ship_to_country=args.country or settings.ship_to_country,
        currency=args.currency or settings.currency,
        page=args.page,
        limit=args.limit,
    )

    try:
        raw_deals = await provider.search(query)
    except ProviderError as exc:
        console.print(f"[red]Provider error:[/red] {exc}")
        return 1

    deals = filter_and_sort_deals(raw_deals, query)

    if args.save:
        monitor = PriceMonitor(settings.db_path)
        alerts = monitor.record_deals(deals, target_max_total_cost=args.max_total_cost)
        for alert in alerts:
            console.print(f"[bold yellow][ALERT][/bold yellow] {alert.title}: {alert.message}")

    if args.json:
        print(json.dumps([d.model_dump(mode="json") for d in deals], indent=2, ensure_ascii=False))
    else:
        _render_deals_table(deals, query.keyword)
    return 0


async def _run_watch(args: argparse.Namespace) -> int:
    settings = get_settings()
    monitor = PriceMonitor(settings.db_path)
    if args.action == "add":
        monitor.add_watch(args.keyword, max_total_cost=args.max_total_cost)
        console.print(f"[green]Added watch:[/green] '{args.keyword}' (target <= {args.max_total_cost})")
    elif args.action == "list":
        watches = monitor.list_watches()
        for w in watches:
            console.print(f"- #{w['id']} [bold]{w['keyword']}[/bold] | target <= {w['max_total_cost']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aliexpress-deals", description="AliExpress Deals Finder CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("search", help="Search and rank AliExpress deals")
    s.add_argument("keyword", help="Search query")
    s.add_argument("--provider", choices=["web", "rapidapi", "official", "mock"], default=None)
    s.add_argument("--min-price", type=float, default=None)
    s.add_argument("--max-price", type=float, default=None)
    s.add_argument("--max-total-cost", type=float, default=None, help="Max (price + shipping)")
    s.add_argument("--free-shipping", action="store_true")
    s.add_argument("--min-discount", type=float, default=None)
    s.add_argument("--min-rating", type=float, default=None)
    s.add_argument("--min-orders", type=int, default=None)
    s.add_argument("--coupons-only", action="store_true")
    s.add_argument("--sort", choices=[e.value for e in SortBy], default=SortBy.BEST_DEAL.value)
    s.add_argument("--country", default=None)
    s.add_argument("--currency", default=None)
    s.add_argument("--page", type=int, default=1)
    s.add_argument("--limit", type=int, default=20)
    s.add_argument("--save", action="store_true", help="Save snapshots to SQLite and emit alerts")
    s.add_argument("--json", action="store_true", help="Output JSON instead of table")

    w = sub.add_parser("watch", help="Manage watched keywords")
    w_sub = w.add_subparsers(dest="action", required=True)
    w_add = w_sub.add_parser("add", help="Add keyword to watchlist")
    w_add.add_argument("keyword")
    w_add.add_argument("--max-total-cost", type=float, default=None)
    w_sub.add_parser("list", help="List watched keywords")

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "search":
        return asyncio.run(_run_search(args))
    if args.command == "watch":
        return asyncio.run(_run_watch(args))
    return 1


if __name__ == "__main__":
    sys.exit(main())
