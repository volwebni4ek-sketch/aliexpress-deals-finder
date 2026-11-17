from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Optional

from rich.console import Console
from rich.table import Table

from aliexpress_deals.arbitrage import CustomsMode, estimate_landed_cost
from aliexpress_deals.config import get_settings
from aliexpress_deals.exporter import export_arbitrage_to_csv, export_arbitrage_to_json
from aliexpress_deals.filters import filter_and_sort_deals
from aliexpress_deals.models import Coupon, SearchQuery, SortBy
from aliexpress_deals.monitor import PriceMonitor
from aliexpress_deals.presets import EQUIPMENT_PRESETS
from aliexpress_deals.providers import build_provider
from aliexpress_deals.providers.base import ProviderError
from aliexpress_deals.telegram_promos import TelegramPromoScraper

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


def _render_arbitrage_table(rows: list[dict], title: str) -> None:
    table = Table(title=title)
    table.add_column("Route", style="bold cyan")
    table.add_column("Title", max_width=36)
    table.add_column("Sale $", justify="right", style="green")
    table.add_column("Coupon", justify="right", style="magenta")
    table.add_column("Ali Ship", justify="right")
    table.add_column("Fwd Ship", justify="right")
    table.add_column("Customs", justify="right")
    table.add_column("Landed $", justify="right", style="bold yellow")
    table.add_column("Rating", justify="right")
    table.add_column("Orders", justify="right")

    for r in rows:
        coupon_str = (
            f"-${r['coupon_discount_usd']:.2f} ({r['applied_coupon_code']})"
            if r["coupon_discount_usd"] > 0 and r["applied_coupon_code"]
            else "-"
        )
        table.add_row(
            r["route_country"],
            r["title"],
            f"${r['sale_price_usd']:.2f}",
            coupon_str,
            f"${r['ali_shipping_usd']:.2f}",
            f"${r['forwarder_shipping_usd']:.2f}",
            f"${r['customs_tax_usd']:.2f}",
            f"${r['final_landed_cost_usd']:.2f}",
            f"{r['rating']:.1f}" if r["rating"] else "-",
            str(r["orders_count"]),
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


async def _fetch_telegram_coupons(channels: list[str]) -> tuple[list[Coupon], list]:
    if not channels:
        return [], []
    scraper = TelegramPromoScraper(channels=channels)
    all_posts = []
    all_coupons: list[Coupon] = []
    for ch in channels:
        try:
            posts = await scraper.fetch_channel_posts(ch)
            all_posts.extend(posts)
            for p in posts:
                all_coupons.extend(p.coupons)
        except Exception as exc:
            console.print(f"[yellow]Warning:[/yellow] failed to fetch @{ch}: {exc}")
    return all_coupons, all_posts


async def _run_preset(args: argparse.Namespace) -> int:
    if args.list or args.preset_slug in (None, "list"):
        table = Table(title="Available Equipment Presets")
        table.add_column("Slug", style="bold cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Routes")
        table.add_column("Weight (kg)", justify="right")
        table.add_column("Customs Mode")
        for slug, preset in EQUIPMENT_PRESETS.items():
            table.add_row(
                slug,
                preset.name_uk,
                ", ".join(preset.recommended_countries),
                f"{preset.estimated_weight_kg:.2f}",
                preset.customs_mode.value,
            )
        console.print(table)
        return 0

    if args.preset_slug == "all":
        target_presets = list(EQUIPMENT_PRESETS.values())
    elif args.preset_slug in EQUIPMENT_PRESETS:
        target_presets = [EQUIPMENT_PRESETS[args.preset_slug]]
    else:
        console.print(
            f"[red]Unknown preset:[/red] '{args.preset_slug}'. "
            f"Available: {', '.join(EQUIPMENT_PRESETS.keys())}, all"
        )
        return 1

    settings = get_settings()
    provider_name = args.provider or settings.provider
    provider = build_provider(provider_name, settings)
    monitor = PriceMonitor(settings.db_path)

    channels: list[str] = []
    for item in args.telegram_channel or []:
        for ch in item.split(","):
            ch_clean = ch.strip().lstrip("@")
            if ch_clean and ch_clean not in channels:
                channels.append(ch_clean)

    telegram_coupons, telegram_posts = await _fetch_telegram_coupons(channels)
    if telegram_posts:
        saved_promos = monitor.save_telegram_promos(telegram_posts)
        console.print(f"[cyan]Loaded {len(telegram_coupons)} Telegram coupons ({saved_promos} saved to SQLite)[/cyan]")

    all_rows: list[dict] = []
    for preset in target_presets:
        countries = (
            [c.strip().upper() for c in args.countries.split(",") if c.strip()]
            if args.countries
            else preset.recommended_countries
        )
        customs_mode = CustomsMode(args.customs_mode) if args.customs_mode else preset.customs_mode

        for kw in preset.search_keywords:
            for country in countries:
                query = SearchQuery(
                    keyword=kw,
                    min_rating=preset.min_rating,
                    ship_to_country=country,
                    currency=settings.currency,
                    limit=args.limit,
                )
                try:
                    raw_deals = await provider.search(query)
                except ProviderError as exc:
                    console.print(f"[yellow]Provider warning ({kw} / {country}):[/yellow] {exc}")
                    continue

                deals = filter_and_sort_deals(raw_deals, query)
                if args.save and deals:
                    monitor.record_deals(deals)

                for d in deals:
                    landed = estimate_landed_cost(
                        d,
                        route_country=country,
                        estimated_weight_kg=preset.estimated_weight_kg,
                        customs_mode=customs_mode,
                        extra_coupons=telegram_coupons,
                    )
                    all_rows.append(
                        {
                            "preset_slug": preset.slug,
                            "keyword": kw,
                            "route_country": landed.route_country,
                            "product_id": d.product_id,
                            "title": d.title,
                            "sale_price_usd": landed.sale_price_usd,
                            "applied_coupon_code": landed.applied_coupon_code or "",
                            "coupon_discount_usd": landed.coupon_discount_usd,
                            "ali_shipping_usd": landed.ali_shipping_usd,
                            "forwarder_shipping_usd": landed.forwarder_shipping_usd,
                            "customs_tax_usd": landed.customs_tax_usd,
                            "final_landed_cost_usd": landed.final_landed_cost_usd,
                            "rating": d.rating,
                            "orders_count": d.orders_count,
                            "deal_score": d.deal_score,
                            "notes": landed.notes,
                            "url": d.url,
                        }
                    )

    all_rows.sort(key=lambda r: r["final_landed_cost_usd"])

    if args.export_csv:
        out_csv = export_arbitrage_to_csv(all_rows, args.export_csv)
        console.print(f"[green]Exported CSV:[/green] {out_csv} ({len(all_rows)} rows)")
    if args.export_json:
        out_json = export_arbitrage_to_json(all_rows, args.export_json)
        console.print(f"[green]Exported JSON:[/green] {out_json} ({len(all_rows)} rows)")

    if args.json:
        print(json.dumps(all_rows, indent=2, ensure_ascii=False))
    else:
        title_slug = args.preset_slug
        _render_arbitrage_table(all_rows[:30], f"Preset '{title_slug}' Landed Cost Comparison ({len(all_rows)} total)")
        if all_rows:
            best = all_rows[0]
            ua_rows = [r for r in all_rows if r["route_country"] == "UA"]
            console.print(
                f"[bold green]Best overall:[/bold green] [{best['route_country']}] "
                f"{best['title']} -> [bold yellow]${best['final_landed_cost_usd']:.2f}[/bold yellow] ({best['notes']})"
            )
            if ua_rows and ua_rows[0] is not best:
                best_ua = ua_rows[0]
                diff = round(best_ua["final_landed_cost_usd"] - best["final_landed_cost_usd"], 2)
                console.print(
                    f"[cyan]Best direct UA:[/cyan] {best_ua['title']} -> "
                    f"${best_ua['final_landed_cost_usd']:.2f} (+${diff:.2f} vs {best['route_country']})"
                )
    return 0


async def _run_promos(args: argparse.Namespace) -> int:
    settings = get_settings()
    channels = [c.strip().lstrip("@") for c in args.channels.split(",") if c.strip()]
    if not channels:
        console.print("[red]Please provide at least one channel via --channels[/red]")
        return 1

    coupons, posts = await _fetch_telegram_coupons(channels)
    saved_count = 0
    if not args.no_save and posts:
        monitor = PriceMonitor(settings.db_path)
        saved_count = monitor.save_telegram_promos(posts)

    if args.json:
        payload = [p.model_dump(mode="json") for p in posts]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    table = Table(title=f"Telegram AliExpress Promos ({len(coupons)} coupons from {len(posts)} posts)")
    table.add_column("Channel", style="cyan")
    table.add_column("Code", style="bold yellow")
    table.add_column("Discount", justify="right", style="green")
    table.add_column("Min Spend", justify="right")
    table.add_column("Description", max_width=40)
    table.add_column("Links", max_width=36)

    for p in posts:
        links_str = ", ".join(p.links[:2]) if p.links else "-"
        if p.coupons:
            for c in p.coupons:
                table.add_row(
                    f"@{p.channel}",
                    c.code or "-",
                    f"${c.discount_amount:g}" if c.discount_amount is not None else "-",
                    f"${c.min_spend:g}" if c.min_spend is not None else "-",
                    c.description,
                    links_str,
                )
        else:
            table.add_row(f"@{p.channel}", "-", "-", "-", p.text[:60], links_str)

    console.print(table)
    if not args.no_save:
        console.print(f"[green]Saved {saved_count} promo codes to SQLite ({settings.db_path})[/green]")
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

    p = sub.add_parser("preset", help="Run batch equipment preset search with EU vs UA landed cost comparison")
    p.add_argument("preset_slug", nargs="?", default=None, help="Preset slug (e.g. power_station_2kwh, all, or list)")
    p.add_argument("--list", action="store_true", help="List available equipment presets")
    p.add_argument("--provider", choices=["web", "rapidapi", "official", "mock"], default=None)
    p.add_argument("--countries", default=None, help="Comma-separated country codes override (e.g. PL,DE,UA)")
    p.add_argument(
        "--telegram-channel",
        action="append",
        default=[],
        help="Telegram channel(s) to scrape promo codes from (can repeat or comma-separate)",
    )
    p.add_argument("--customs-mode", choices=[e.value for e in CustomsMode], default=None)
    p.add_argument("--limit", type=int, default=10, help="Max deals per keyword/country")
    p.add_argument("--export-csv", default=None, help="Export comparison results to CSV")
    p.add_argument("--export-json", default=None, help="Export comparison results to JSON")
    p.add_argument("--save", action="store_true", help="Save deal snapshots to SQLite")
    p.add_argument("--json", action="store_true", help="Output JSON instead of table")

    pr = sub.add_parser("promos", help="Scrape AliExpress promo codes from public Telegram channels (t.me/s/...)")
    pr.add_argument("--channels", required=True, help="Comma-separated Telegram channel usernames")
    pr.add_argument("--no-save", action="store_true", help="Do not persist extracted promos to SQLite")
    pr.add_argument("--json", action="store_true", help="Output JSON instead of table")

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
    if args.command == "preset":
        return asyncio.run(_run_preset(args))
    if args.command == "promos":
        return asyncio.run(_run_promos(args))
    if args.command == "watch":
        return asyncio.run(_run_watch(args))
    return 1


if __name__ == "__main__":
    sys.exit(main())
