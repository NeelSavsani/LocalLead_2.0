import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Optional API Keys
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    GOOGLE_SEARCH_API_KEY: Optional[str] = None
    GOOGLE_SEARCH_ENGINE_ID: Optional[str] = None

    # Application Settings
    DEFAULT_SEARCH_RADIUS_KM: int = 10
    DEFAULT_LEAD_LIMIT: int = 20
    MAX_LEAD_LIMIT: int = 100
    HEADLESS_BROWSER: bool = True
    MOCK_MODE: bool = False

    # Paths
    EXPORTS_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports"
    )

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
os.makedirs(settings.EXPORTS_DIR, exist_ok=True)
