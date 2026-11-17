from __future__ import annotations

from aliexpress_deals.config import Settings
from aliexpress_deals.providers.base import AliExpressProvider, ProviderError
from aliexpress_deals.providers.mock import MockProvider
from aliexpress_deals.providers.official import OfficialOpenPlatformProvider
from aliexpress_deals.providers.rapidapi import RapidApiScraperProvider
from aliexpress_deals.providers.web_search import DirectWebSearchProvider


def build_provider(provider_name: str, settings: Settings) -> AliExpressProvider:
    name = provider_name.lower().strip()
    if name == "web":
        return DirectWebSearchProvider()
    if name == "mock":
        return MockProvider()
    if name == "rapidapi":
        return RapidApiScraperProvider(api_key=settings.rapidapi_key, host=settings.rapidapi_host)
    if name == "official":
        return OfficialOpenPlatformProvider(
            app_key=settings.app_key,
            app_secret=settings.app_secret,
            tracking_id=settings.tracking_id or "default",
        )
    raise ProviderError(f"Unknown provider '{provider_name}'. Choose from: web, rapidapi, official, mock.")
