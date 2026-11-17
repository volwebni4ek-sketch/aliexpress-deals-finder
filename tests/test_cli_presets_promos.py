import json
from pathlib import Path

from aliexpress_deals import cli
from aliexpress_deals.models import Coupon
from aliexpress_deals.monitor import PriceMonitor
from aliexpress_deals.telegram_promos import TelegramDealPost, TelegramPromoScraper


def test_cli_preset_list(capsys):
    rc = cli.main(["preset", "--list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "power_station_2kwh" in out
    assert "multimeter" in out


def test_cli_preset_mock_export_csv_and_json(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AE_DB_PATH", str(db_path if "db_path" in locals() else tmp_path / "test.db"))
    csv_path = tmp_path / "deals.csv"
    json_path = tmp_path / "deals.json"

    rc = cli.main(
        [
            "preset",
            "power_station_2kwh",
            "--provider",
            "mock",
            "--export-csv",
            str(csv_path),
            "--export-json",
            str(json_path),
        ]
    )
    assert rc == 0
    assert csv_path.exists()
    assert json_path.exists()

    rows = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(rows) > 0
    routes = {r["route_country"] for r in rows}
    assert {"PL", "DE", "UA"}.issubset(routes)
    assert all("final_landed_cost_usd" in r for r in rows)


def test_cli_promos_saves_to_sqlite(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "promos.db"
    monkeypatch.setenv("AE_DB_PATH", str(db_path))

    async def fake_fetch(self, channel: str):
        return [
            TelegramDealPost(
                channel=channel,
                text="Промокод: SAVE30 — $30 off $200",
                links=["https://s.click.aliexpress.com/e/_test123"],
                coupons=[
                    Coupon(
                        code="SAVE30",
                        description="SAVE30: $30 off $200 (from @test_chan)",
                        discount_amount=30.0,
                        min_spend=200.0,
                    )
                ],
            )
        ]

    monkeypatch.setattr(TelegramPromoScraper, "fetch_channel_posts", fake_fetch)

    rc = cli.main(["promos", "--channels", "test_chan"])
    assert rc == 0

    monitor = PriceMonitor(db_path)
    saved = monitor.list_telegram_promos()
    assert len(saved) == 1
    assert saved[0]["code"] == "SAVE30"
    assert saved[0]["channel"] == "test_chan"
    assert saved[0]["discount_amount"] == 30.0
