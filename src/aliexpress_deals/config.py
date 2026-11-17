from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env."""

    model_config = SettingsConfigDict(
        env_prefix="AE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    provider: str = "web"
    ship_to_country: str = "UA"
    currency: str = "USD"
    language: str = "en_US"
    db_path: str = "deals.db"

    # Optional RapidAPI settings
    rapidapi_key: str = ""
    rapidapi_host: str = "aliexpress-scraper-api1.p.rapidapi.com"

    # Optional Official AliExpress Open Platform settings
    app_key: str = ""
    app_secret: str = ""
    tracking_id: str = ""


def get_settings() -> Settings:
    return Settings()
