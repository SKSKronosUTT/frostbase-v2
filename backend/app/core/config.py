from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_SECRET_LENGTH = 64
MIN_ADMIN_PASSWORD_LENGTH = 12
INSECURE_SECRET_PREFIXES = ("dev-only", "cambia-")


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
    auto_create_tables: bool = False

    # Los secretos son obligatorios: sin ellos el proceso no arranca.
    secret_key: str
    device_key_pepper: str
    device_key_fast_path: bool = True
    access_token_expire_minutes: int = 60
    cookie_name: str = "frostbase_token"
    csrf_cookie_name: str = "frostbase_csrf"
    cookie_secure: bool = True
    cookie_samesite: str = "lax"

    admin_username: str = "admin"
    admin_email: str = "admin@frostbase.local"
    admin_password: str

    rate_limit_backend: Literal["memory", "redis"] = "memory"
    redis_url: str = ""

    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    log_level: str = "INFO"

    cors_origins: str = (
        "http://localhost:8050,http://127.0.0.1:8050,"
        "http://localhost:8060,http://127.0.0.1:8060,"
        "http://localhost:8070,http://127.0.0.1:8070"
    )

    device_offline_seconds: int = 60
    dashboard_fresh_minutes: int = 10
    disconnect_check_seconds: int = 30
    enable_inprocess_watcher: bool = False

    osrm_base_url: str = "https://router.project-osrm.org"
    osrm_timeout_seconds: float = 5.0
    weather_timeout_seconds: float = 3.0

    weather_city: str = "Tijuana"
    weather_latitude: float = 32.5149
    weather_longitude: float = -117.0382
    weather_cache_seconds: int = 600

    route_geometry_async: bool = False

    frontend_dir: str = ""

    @field_validator("secret_key", "device_key_pepper")
    @classmethod
    def _strong_secret(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < MIN_SECRET_LENGTH or normalized.startswith(
            INSECURE_SECRET_PREFIXES
        ):
            raise ValueError(
                f"debe ser aleatoria y de al menos {MIN_SECRET_LENGTH} caracteres "
                f"(rechazado el prefijo {INSECURE_SECRET_PREFIXES})"
            )
        return normalized

    @field_validator("admin_password")
    @classmethod
    def _strong_admin_password(cls, value: str) -> str:
        if len(value) < MIN_ADMIN_PASSWORD_LENGTH:
            raise ValueError(
                "debe tener al menos "
                f"{MIN_ADMIN_PASSWORD_LENGTH} caracteres"
            )
        if value == "ChangeMe123!":
            raise ValueError("no puede ser la contraseña por defecto del proyecto")
        return value

    @model_validator(mode="after")
    def _production_coherence(self) -> "Settings":
        if self.is_production:
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE debe ser true en producción")
            if self.cookie_samesite.lower() not in {"lax", "strict"}:
                raise ValueError(
                    "COOKIE_SAMESITE debe ser 'lax' o 'strict' en producción"
                )
            if self.auto_create_tables:
                raise ValueError("AUTO_CREATE_TABLES debe ser false en producción")
            if "*" in self.cors_origin_list:
                raise ValueError("CORS_ORIGINS no admite '*' con credenciales")
        return self

    @property
    def frontend_path(self) -> Path:
        if self.frontend_dir:
            return Path(self.frontend_dir).resolve()
        return (Path(__file__).resolve().parents[3] / "frontend").resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
