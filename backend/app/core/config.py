from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
    # Siembra datos de demostración al inicializar (solo desarrollo/demo).
    seed_demo_data: bool = False

    # Los secretos son obligatorios: sin ellos el proceso no arranca.
    secret_key: str
    device_key_pepper: str
    device_key_fast_path: bool = True
    access_token_expire_minutes: int = 60
    cookie_name: str = "frostbase_token"
    csrf_cookie_name: str = "frostbase_csrf"
    cookie_secure: bool = True
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"

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

    dashboard_fresh_minutes: int = 10
    disconnect_check_seconds: int = 30
    door_check_seconds: int = 5
    enable_inprocess_watcher: bool = False
    readings_retention_days: int = 90
    resolved_alerts_retention_days: int = 365
    retention_check_seconds: int = 86400
    iot_device_rate_limit: int = 30
    iot_ip_rate_limit: int = 120
    login_ip_rate_limit: int = 5
    login_identifier_rate_limit: int = 10
    hash_concurrency: int = 2

    # Asistente IA (ESP-Claw). Deshabilitado por defecto.
    ai_agent_enabled: bool = False
    ai_agent_url: str = ""
    ai_agent_token: str = ""
    ai_agent_timeout_seconds: int = 90
    ai_agent_connect_timeout_seconds: float = 5.0
    ai_agent_poll_interval_seconds: float = 1.0
    ai_agent_max_message_chars: int = 500
    ai_agent_max_reply_chars: int = 4000
    ai_agent_max_conversations: int = 5
    ai_agent_rate_limit: int = 6
    ai_agent_daily_limit: int = 100
    ai_agent_status_cache_seconds: int = 15
    # Sonda de ``boot_id`` por consulta: detecta reinicios del ESP32 y rota la
    # sesión antes de fallar. Corta para no añadir latencia perceptible.
    ai_agent_boot_probe_seconds: float = 2.0
    # Cortacircuito: tras N fallos seguidos se deja de llamar al agente durante
    # ``AI_AGENT_BREAKER_SECONDS`` (respuesta 503 inmediata con Retry-After).
    ai_agent_breaker_failures: int = 3
    ai_agent_breaker_seconds: int = 30
    ai_agent_read_token: str = ""
    # El agente llama al backend por su IP de LAN; se usa para generar el
    # prompt de operación (scripts.agent_prompt).
    ai_backend_url: str = ""
    # Rotación de la sesión del agente para limitar la memoria acumulada.
    ai_agent_session_ttl_hours: int = 12
    # Retención de la auditoría (solo metadatos, sin contenido) y de las
    # conversaciones cerradas o inactivas (tampoco guardan contenido).
    ai_audit_retention_days: int = 90
    ai_conversations_retention_days: int = 30

    osrm_base_url: str = "https://router.project-osrm.org"
    osrm_timeout_seconds: float = 5.0
    weather_timeout_seconds: float = 3.0
    weather_cache_seconds: int = 600

    route_geometry_async: bool = False

    app_timezone: str = "America/Tijuana"

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
                f"debe tener al menos {MIN_ADMIN_PASSWORD_LENGTH} caracteres"
            )
        if value == "ChangeMe123!":
            raise ValueError("no puede ser la contraseña por defecto del proyecto")
        return value

    @field_validator("app_timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        normalized = value.strip()
        try:
            ZoneInfo(normalized)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"zona horaria desconocida: {normalized}") from exc
        return normalized

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
            if self.seed_demo_data:
                raise ValueError("SEED_DEMO_DATA debe ser false en producción")
            if "*" in self.cors_origin_list:
                raise ValueError("CORS_ORIGINS no admite '*' con credenciales")
        return self

    @property
    def frontend_path(self) -> Path:
        if self.frontend_dir:
            return Path(self.frontend_dir).resolve()
        root = Path(__file__).resolve().parents[3] / "frontend"
        build = root / "build"
        return build if (build / "index.html").exists() else root

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]

    @property
    def allowed_host_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}

    @property
    def tz(self) -> ZoneInfo:
        """Zona horaria de negocio (calendario semanal de rutas)."""
        return ZoneInfo(self.app_timezone)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
