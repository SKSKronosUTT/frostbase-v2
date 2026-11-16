from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    project_name: str = "FrostBase"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"

    database_url: str = (
        "postgresql+psycopg://frostbase:frostbase@localhost:5432/frostbase"
    )
    auto_create_tables: bool = True

    secret_key: str = "dev-only-change-this-secret-key"
    access_token_expire_minutes: int = 720
    cookie_name: str = "frostbase_token"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    admin_username: str = "admin"
    admin_email: str = "admin@frostbase.local"
    admin_password: str = "ChangeMe123!"

    cors_origins: str = (
        "http://localhost:8000,http://127.0.0.1:8000,"
        "http://localhost:8010,http://127.0.0.1:8010"
    )

    device_offline_seconds: int = 60
    dashboard_fresh_minutes: int = 10
    disconnect_check_seconds: int = 30

    osrm_base_url: str = "https://router.project-osrm.org"
    osrm_timeout_seconds: float = 15.0

    weather_city: str = "Tijuana"
    weather_latitude: float = 32.5149
    weather_longitude: float = -117.0382
    weather_cache_seconds: int = 600

    frontend_dir: str = ""

    @property
    def frontend_path(self) -> Path:
        if self.frontend_dir:
            return Path(self.frontend_dir).resolve()
        return (Path(__file__).resolve().parents[3] / "frontend").resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
