"""Esquemas del módulo de carga de firmware."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.presentation.schemas.common import ORMModel


class FirmwareReleaseOut(ORMModel):
    id: int
    version: str
    size_bytes: int
    sha256: str
    notes: str | None
    uploaded_by: str
    created_at: datetime
    assigned_devices: int = Field(description="Estaciones que tienen asignada esta versión")


class FirmwareAssignmentIn(BaseModel):
    release_id: int | None = Field(description="Versión a instalar; vacío para no actualizar")
    device_ids: list[int] = Field(min_length=1, max_length=200)


class FlashPartOut(BaseModel):
    name: str
    address: int = Field(description="Dirección en la memoria flash del ESP32")
    size: int
    sha256: str


class FirstInstallIn(BaseModel):
    device_id: int
    release_id: int


class FirstInstallOut(BaseModel):
    device_code: str
    api_key: str = Field(description="Credencial nueva; el navegador la envía al ESP32 sin mostrarla")
    sample_interval_s: int
    version: str
    wifi_password: str | None = Field(
        description="Contraseña Wi-Fi guardada en el servidor (si la hay); el navegador la envía al ESP32 sin mostrarla"
    )


class StationDefaultsOut(BaseModel):
    wifi_ssid: str
    wifi_password_saved: bool
    api_url: str
    ntp_server: str
