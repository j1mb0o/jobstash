from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and `.env`."""

    database_url: str = "sqlite:///jobs.db"
    app_host: str = "127.0.0.1"
    app_port: int = 1234
    log_level: str = "INFO"
    default_location: str = "Netherlands"
    default_request_delay_seconds: float = 3.0
    default_fetch_descriptions: bool = True
    default_seniority: str = "Junior"
    openrouter_api_key: str = ""
    openrouter_model: str = "nvidia/nemotron-3.5-lightning:free"
    cv_path: str = "data/Dimitrios_Kourntidis_CV.md"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
