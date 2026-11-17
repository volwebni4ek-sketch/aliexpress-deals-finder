from __future__ import annotations

import html as html_lib
import re
from typing import Optional

import httpx
from pydantic import BaseModel, Field

from aliexpress_deals.models import Coupon

_MSG_BLOCK_RE = re.compile(
    r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
    re.DOTALL | re.IGNORECASE,
)
_TAG_STRIP_RE = re.compile(r"<[^>]+>")
_ALI_LINK_RE = re.compile(
    r"https?://(?:s\.click\.aliexpress\.com|a\.aliexpress\.com|(?:www\.)?aliexpress\.com)/[^\s\"'<>]+",
    re.IGNORECASE,
)
# Matches patterns like "$5 off $30", "5$ від 30$", "-$10 на замовлення від $80"
_THRESHOLD_RE = re.compile(
    r"(?:\$|USD\s*)?(\d+(?:[.,]\d+)?)\s*(?:\$|USD)?\s*(?:off|від|from|на|при замовленні від|/)\s*(?:\$|USD\s*)?(\d+(?:[.,]\d+)?)",
    re.IGNORECASE,
)
# Matches promo codes near keywords or standalone uppercase tokens
_CODE_LINE_RE = re.compile(
    r"(?:промокод|код|code|coupon|купон)[:\s\-–—]*([A-Z0-9]{4,16})\b",
    re.IGNORECASE,
)


class TelegramDealPost(BaseModel):
    channel: str
    text: str
    links: list[str] = Field(default_factory=list)
    coupons: list[Coupon] = Field(default_factory=list)


def parse_telegram_channel_html(raw_html: str, channel: str = "unknown") -> list[TelegramDealPost]:
    """Extract deal posts, AliExpress links, and promo codes from public t.me/s/<channel> HTML."""
    posts: list[TelegramDealPost] = []
    for match in _MSG_BLOCK_RE.finditer(raw_html):
        block = match.group(1)
        links = _ALI_LINK_RE.findall(block)
        clean_text = html_lib.unescape(_TAG_STRIP_RE.sub(" ", block))
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
        if not clean_text:
            continue

        codes = _CODE_LINE_RE.findall(clean_text)
        thresholds = _THRESHOLD_RE.findall(clean_text)

        coupons: list[Coupon] = []
        if codes and thresholds:
            disc_str, min_str = thresholds[0]
            disc = float(disc_str.replace(",", "."))
            min_sp = float(min_str.replace(",", "."))
            for code in dict.fromkeys(c.upper() for c in codes):
                coupons.append(
                    Coupon(
                        code=code,
                        description=f"{code}: ${disc:g} off ${min_sp:g} (from @{channel})",
                        discount_amount=disc,
                        min_spend=min_sp,
                    )
                )
        elif codes:
            for code in dict.fromkeys(c.upper() for c in codes):
                coupons.append(
                    Coupon(
                        code=code,
                        description=f"Promo code {code} (from @{channel})",
                    )
                )

        if links or coupons:
            posts.append(
                TelegramDealPost(
                    channel=channel,
                    text=clean_text[:500],
                    links=list(dict.fromkeys(links)),
                    coupons=coupons,
                )
            )
    return posts


class TelegramPromoScraper:
    """Scrapes public Telegram deal channels via https://t.me/s/<channel> without API keys."""

    def __init__(self, channels: Optional[list[str]] = None, timeout: float = 15.0) -> None:
        self.channels = channels or []
        self.timeout = timeout

    async def fetch_channel_posts(self, channel: str) -> list[TelegramDealPost]:
        clean_channel = channel.lstrip("@").strip()
        url = f"https://t.me/s/{clean_channel}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            )
        }
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return parse_telegram_channel_html(resp.text, channel=clean_channel)
