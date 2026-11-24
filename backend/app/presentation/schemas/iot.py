"""Esquemas de infraestructura, dispositivos, sensores, mediciones y dashboard."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field

from app.presentation.schemas.common import ORMModel

CODE_PATTERN = r"^[A-Za-z0-9_.-]{2,40}$"
DeviceStatus = Literal["activo", "inactivo", "mantenimiento"]
Bucket = Literal["hour", "day", "week", "month"]
SampleInterval = Literal[5, 30, 60]
Connection = Literal["al_dia", "desactualizado", "sin_comunicacion"]
Orientation = Literal["N", "NE", "E", "SE", "S", "SO", "O", "NO"]


# --- Infraestructura -------------------------------------------------------


class LocationIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    altitude_m: Decimal | None = Field(default=None, ge=-500, le=9000)


class LocationUpdate(LocationIn):
    name: str | None = Field(default=None, min_length=2, max_length=120)  # type: ignore[assignment]
    is_active: bool | None = None


class LocationOut(ORMModel):
    id: int
    name: str
    description: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    altitude_m: Decimal | None
    is_active: bool


class FogCollectorIn(BaseModel):
    code: str = Field(pattern=CODE_PATTERN)
    name: str = Field(min_length=2, max_length=120)
    location_id: int | None = None
    mesh_area_m2: Decimal | None = Field(default=None, gt=0, le=10_000)
    mesh_type: str | None = Field(default=None, max_length=80)
    orientation: Orientation | None = Field(default=None, description="Orientación de la malla, p. ej. NE")
    installed_on: date | None = None


class FogCollectorUpdate(BaseModel):
    code: str | None = Field(default=None, pattern=CODE_PATTERN)
    name: str | None = Field(default=None, min_length=2, max_length=120)
    location_id: int | None = None
    mesh_area_m2: Decimal | None = Field(default=None, gt=0, le=10_000)
    mesh_type: str | None = Field(default=None, max_length=80)
    orientation: str | None = Field(default=None, max_length=40, description="Orientación de la malla, p. ej. NE")
    installed_on: date | None = None
    is_active: bool | None = None


class FogCollectorOut(ORMModel):
    id: int
    code: str
    name: str
    location_id: int | None
    mesh_area_m2: Decimal | None
    mesh_type: str | None
    orientation: str | None
    installed_on: date | None
    is_active: bool


class TankIn(BaseModel):
    code: str = Field(pattern=CODE_PATTERN)
    name: str = Field(min_length=2, max_length=120)
    location_id: int | None = None
    fog_collector_id: int | None = None
    capacity_liters: Decimal | None = Field(default=None, gt=0)
    height_cm: Decimal | None = Field(default=None, gt=0)


class TankUpdate(BaseModel):
    code: str | None = Field(default=None, pattern=CODE_PATTERN)
    name: str | None = Field(default=None, min_length=2, max_length=120)
    location_id: int | None = None
    fog_collector_id: int | None = None
    capacity_liters: Decimal | None = Field(default=None, gt=0)
    height_cm: Decimal | None = Field(default=None, gt=0)
    is_active: bool | None = None


class TankOut(ORMModel):
    id: int
    code: str
    name: str
    location_id: int | None
    fog_collector_id: int | None
    capacity_liters: Decimal | None
    height_cm: Decimal | None
    is_active: bool


class GreenhouseIn(BaseModel):
    code: str = Field(pattern=CODE_PATTERN)
    name: str = Field(min_length=2, max_length=120)
    location_id: int | None = None
    area_m2: Decimal | None = Field(default=None, gt=0)
    tank_id: int | None = None


class GreenhouseUpdate(BaseModel):
    code: str | None = Field(default=None, pattern=CODE_PATTERN)
    name: str | None = Field(default=None, min_length=2, max_length=120)
    location_id: int | None = None
    area_m2: Decimal | None = Field(default=None, gt=0)
    tank_id: int | None = None
    is_active: bool | None = None


class GreenhouseOut(ORMModel):
    id: int
    code: str
    name: str
    location_id: int | None
    area_m2: Decimal | None
    tank_id: int | None
    is_active: bool


# --- Dispositivos y sensores -----------------------------------------------


class DeviceIn(BaseModel):
    code: str = Field(pattern=CODE_PATTERN, description="Identidad única del ESP32 (X-Device-Id).")
    name: str = Field(min_length=2, max_length=120)
    description: str | None = None
    fog_collector_id: int | None = None
    location_id: int | None = None


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = None
    fog_collector_id: int | None = None
    location_id: int | None = None
    status: DeviceStatus | None = None
    sample_interval_s: SampleInterval | None = Field(
        default=None, description="Segundos entre lecturas: 5 (tiempo real), 30 o 60"
    )


class DeviceOut(ORMModel):
    id: int
    code: str
    name: str
    description: str | None
    firmware_version: str | None
    target_firmware_version: str | None = Field(default=None, description="Versión asignada para instalar por OTA")
    status: str
    fog_collector_id: int | None
    last_seen_at: datetime | None
    sample_interval_s: int
    created_at: datetime


class DeviceWithKeyOut(BaseModel):
    device: DeviceOut
    api_key: str = Field(description="Se muestra una sola vez; cárguela en la configuración segura del firmware.")


class SensorTypeOut(ORMModel):
    id: int
    code: str
    name: str
    unit: str
    min_value: float
    max_value: float
    aggregation: str
    description: str | None


class SensorIn(BaseModel):
    device_id: int
    sensor_type_id: int
    code: str = Field(pattern=CODE_PATTERN, description="Código usado por el firmware en cada lectura.")
    model: str | None = Field(default=None, max_length=80)
    fog_collector_id: int | None = None
    tank_id: int | None = None


class SensorUpdate(BaseModel):
    code: str | None = Field(default=None, pattern=CODE_PATTERN)
    model: str | None = Field(default=None, max_length=80)
    fog_collector_id: int | None = None
    tank_id: int | None = None
    status: DeviceStatus | None = None


class SensorOut(ORMModel):
    id: int
    device_id: int
    sensor_type_id: int
    code: str
    model: str | None
    status: str
    fog_collector_id: int | None
    tank_id: int | None
    sensor_type: SensorTypeOut


# --- Ingesta IoT -----------------------------------------------------------


class ReadingIn(BaseModel):
    message_id: uuid.UUID = Field(description="Identificador único de la lectura generado por el ESP32.")
    sensor_code: str = Field(pattern=CODE_PATTERN)
    measured_at: AwareDatetime = Field(description="Fecha de medición ISO 8601 con zona horaria.")
    value: float | None = Field(allow_inf_nan=False, description="null cuando la variable no fue medida.")
    unit: str = Field(min_length=1, max_length=16)


class BatchIn(BaseModel):
    batch_id: uuid.UUID
    sent_at: AwareDatetime | None = None
    firmware_version: str | None = Field(default=None, max_length=40)
    readings: list[ReadingIn] = Field(min_length=1)


class ReadingResultOut(BaseModel):
    message_id: uuid.UUID
    status: str
    quality: str | None
    detail: str | None


class BatchResultOut(BaseModel):
    batch_id: uuid.UUID
    status: str
    received_at: datetime
    accepted: int
    invalid: int
    rejected: int
    duplicates: int
    results: list[ReadingResultOut]
    sample_interval_s: int = Field(description="Intervalo de muestreo que la estación debe aplicar desde ahora")


class ReadingOut(ORMModel):
    id: int
    message_uid: uuid.UUID
    device_id: int
    sensor_id: int
    sensor_type_id: int
    measured_at: datetime
    received_at: datetime
    value: float | None
    unit: str
    quality: str
    quality_detail: str | None


# --- Dashboard -------------------------------------------------------------


class DeviceStatusOut(BaseModel):
    id: int
    code: str
    name: str
    status: str
    last_seen_at: datetime | None
    minutes_since_last_seen: int | None
    is_stale: bool


class LatestValueOut(BaseModel):
    sensor_id: int
    sensor_code: str
    device_id: int
    sensor_type_code: str
    sensor_type_name: str
    unit: str
    value: float | None
    measured_at: datetime
    is_stale: bool


class VolumeTotalsOut(BaseModel):
    today_liters: float
    last_7_days_liters: float
    month_liters: float


class DashboardSummaryOut(BaseModel):
    generated_at: datetime
    stale_threshold_minutes: int
    last_communication_at: datetime | None
    has_stale_data: bool
    devices: list[DeviceStatusOut]
    latest: list[LatestValueOut]
    volume: VolumeTotalsOut


class SeriesPointOut(BaseModel):
    bucket: datetime
    value: float | None
    min: float | None
    max: float | None
    count: int


class SeriesOut(BaseModel):
    sensor_type: SensorTypeOut
    aggregation: str
    bucket: Bucket
    date_from: datetime
    date_to: datetime
    points: list[SeriesPointOut]


# --- Monitoreo en vivo -------------------------------------------------------


class LivePointOut(BaseModel):
    t: datetime
    v: float


class LiveVariableOut(BaseModel):
    sensor_type: SensorTypeOut
    aggregation: str
    latest_value: float | None
    latest_at: datetime | None
    minimum: float | None
    maximum: float | None
    average: float | None
    points: list[LivePointOut]


class LiveDeviceOut(BaseModel):
    id: int
    code: str
    name: str
    status: str
    last_seen_at: datetime | None
    sample_interval_s: int
    is_stale: bool


class LiveOut(BaseModel):
    generated_at: datetime
    window_minutes: int
    device: LiveDeviceOut
    variables: list[LiveVariableOut]
