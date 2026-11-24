"""Configuración central de la aplicación, cargada desde variables de entorno."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
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
    # Límite por equipo (IP): frena que se prueben muchas cuentas desde un mismo equipo.
    login_max_failed_per_ip: int = 20
    login_ip_window_minutes: int = 15

    # Límites de solicitudes de recuperación de cuenta
    recovery_max_per_ip_per_hour: int = 5
    recovery_max_per_username_per_day: int = 3

    # Zona horaria usada para agrupar por día/semana/mes en reportes y dashboard.
    local_timezone: str = "America/La_Paz"

    # IoT
    measurement_max_future_skew_seconds: int = 300
    device_stale_minutes: int = 30
    max_readings_per_batch: int = 500

    # Incidencias automáticas: el sistema abre un reporte cuando una estación activa deja de comunicarse
    # o un sensor acumula lecturas anómalas. La revisión corre dentro de la API cada N minutos.
    auto_incidents_enabled: bool = True
    auto_incidents_interval_minutes: int = Field(default=15, ge=1)
    auto_incident_offline_hours: int = Field(default=6, ge=1)
    auto_incident_anomaly_window_hours: int = Field(default=24, ge=1)
    auto_incident_anomaly_threshold: int = Field(default=10, ge=1)

    # Bootloader, tabla de particiones y boot_app0 para la primera instalación por USB (ver firmware_base/README.md).
    firmware_base_dir: Path = Path(__file__).resolve().parents[2] / "firmware_base"
    # Datos que la primera instalación precarga en cada estación. La contraseña Wi-Fi se envía solo al
    # ESP32 (por el puerto serie): nunca se muestra en pantalla ni se registra.
    station_wifi_ssid: str = ""
    station_wifi_password: SecretStr = SecretStr("")
    station_api_url: str = ""  # p. ej. http://192.168.1.10/api/v1/iot/measurements/batch
    station_ntp_server: str = ""  # servidor de hora de la red local

    # Modelo de ML (provisional: entrenado con datos simulados). Se carga desde la carpeta controlada de artefactos.
    ml_artifact_path: Path = Path(__file__).resolve().parents[2] / "artifacts" / "modelo_sim-0.1.0.joblib"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
