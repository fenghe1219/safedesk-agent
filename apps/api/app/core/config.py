from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "SafeDesk"
    app_env: str = "development"
    api_prefix: str = "/api"
    api_version: str = "0.1.0"
    database_url: str = "postgresql+psycopg://safedesk:safedesk@localhost:5432/safedesk"
    demo_mode: bool = True
    seed_demo: bool = True
    secret_key: str = "dev-only-change-me"
    session_cookie_name: str = "sd_session"
    csrf_cookie_name: str = "sd_csrf"
    session_cookie_secure: bool = False
    session_ttl_hours: int = 8
    cors_origins: list[str] = ["http://localhost:3000"]
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
