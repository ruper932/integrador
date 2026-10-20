"""Configuración central de la aplicación, cargada desde variables de entorno."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Sistema de Monitoreo de Atrapanieblas"
    environment: str = Field(default="development", description="development | test | production")

    database_url: str = Field(description="URL SQLAlchemy de PostgreSQL (postgresql+psycopg://...)")

    # Clave para firmar (HMAC) los tokens de sesión. Debe ser larga y aleatoria.
    secret_key: str = Field(min_length=32)
    session_ttl_minutes: int = 480
    session_cookie_name: str = "atrapanieblas_session"
    cookie_secure: bool = False  # True cuando Nginx sirva HTTPS en la red local

    cors_origins: list[str] = ["http://localhost:5173"]
    # Solo activar cuando la API está detrás de Nginx y no es accesible directamente.
    trust_proxy_headers: bool = False

    # Protección de inicio de sesión
    login_max_failed_attempts: int = 5
    login_lockout_minutes: int = 15

    # Límites de solicitudes de recuperación de cuenta
    recovery_max_per_ip_per_hour: int = 5
    recovery_max_per_username_per_day: int = 3

    # Zona horaria usada para agrupar por día/semana/mes en reportes y dashboard.
    local_timezone: str = "America/La_Paz"

    # IoT
    measurement_max_future_skew_seconds: int = 300
    device_stale_minutes: int = 30
    max_readings_per_batch: int = 500


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
