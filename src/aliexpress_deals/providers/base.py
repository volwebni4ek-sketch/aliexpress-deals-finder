from __future__ import annotations

from typing import Protocol

from aliexpress_deals.models import ProductDeal, SearchQuery


class ProviderError(Exception):
    """Base error for AliExpress data providers."""


class AntiBotChallengeError(ProviderError):
    """Raised when AliExpress returns a CAPTCHA or anti-bot challenge page."""


class AliExpressProvider(Protocol):
    name: str

    async def search(self, query: SearchQuery) -> list[ProductDeal]:
        """Fetch raw product deals matching the search query."""
        ...
