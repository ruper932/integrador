"""Consulta de históricos y datos del dashboard."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.errors import BusinessRuleError, NotFoundError
from app.data.models.iot import Device, SensorReading, SensorType
from app.data.repositories.iot import DeviceRepository, SensorReadingRepository, SensorTypeRepository

VOLUME_TYPE_CODE = "volumen_captado"
MAX_SERIES_POINTS = 5000


@dataclass(frozen=True)
class DeviceStatus:
    device: Device
    is_stale: bool
    minutes_since_last_seen: int | None


@dataclass(frozen=True)
class LatestValue:
    reading: SensorReading
    is_stale: bool


@dataclass(frozen=True)
class VolumeTotals:
    today_liters: float
    last_7_days_liters: float
    month_liters: float


@dataclass(frozen=True)
class DashboardSummary:
    generated_at: datetime
    stale_threshold_minutes: int
    devices: list[DeviceStatus]
    latest: list[LatestValue]
    volume: VolumeTotals
    last_communication_at: datetime | None


@dataclass(frozen=True)
class SeriesPoint:
    bucket: datetime
    value: float | None
    min: float | None
    max: float | None
    count: int


@dataclass(frozen=True)
class Series:
    sensor_type: SensorType
    bucket: str
    date_from: datetime
    date_to: datetime
    points: list[SeriesPoint]


_BUCKET_SIZES = {
    "hour": timedelta(hours=1),
    "day": timedelta(days=1),
    "week": timedelta(weeks=1),
    "month": timedelta(days=28),
}


class MeasurementService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.readings = SensorReadingRepository(session)
        self.devices = DeviceRepository(session)
        self.sensor_types = SensorTypeRepository(session)
        self.settings = get_settings()
        self.tz = ZoneInfo(self.settings.local_timezone)

    def search(self, **filters: object) -> tuple[Sequence[SensorReading], int]:
        date_from, date_to = filters.get("date_from"), filters.get("date_to")
        if isinstance(date_from, datetime) and isinstance(date_to, datetime) and date_from > date_to:
            raise BusinessRuleError("La fecha inicial debe ser anterior a la final.", code="rango_invalido")
        return self.readings.search(**filters)  # type: ignore[arg-type]

    def _is_stale(self, ts: datetime | None, now: datetime) -> bool:
        return ts is None or now - ts > timedelta(minutes=self.settings.device_stale_minutes)

    def summary(self) -> DashboardSummary:
        now = utcnow()
        devices = [d for d in self.devices.list(limit=1000, order_by=Device.code) if d.status != "inactivo"]
        statuses = [
            DeviceStatus(
                device=d,
                is_stale=self._is_stale(d.last_seen_at, now),
                minutes_since_last_seen=int((now - d.last_seen_at).total_seconds() // 60) if d.last_seen_at else None,
            )
            for d in devices
        ]
        active_ids = {d.id for d in devices}
        latest = [
            LatestValue(reading=r, is_stale=self._is_stale(r.measured_at, now))
            for r in self.readings.latest_valid_per_sensor()
            if r.device_id in active_ids and r.sensor.status == "activo"
        ]
        last_comm = max((d.last_seen_at for d in devices if d.last_seen_at), default=None)
        return DashboardSummary(
            generated_at=now,
            stale_threshold_minutes=self.settings.device_stale_minutes,
            devices=statuses,
            latest=latest,
            volume=self._volume_totals(now),
            last_communication_at=last_comm,
        )

    def _volume_totals(self, now: datetime) -> VolumeTotals:
        volume_type = self.sensor_types.get_by(code=VOLUME_TYPE_CODE)
        if volume_type is None:
            return VolumeTotals(0.0, 0.0, 0.0)
        local_now = now.astimezone(self.tz)
        start_today = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_month = start_today.replace(day=1)
        end = now + timedelta(seconds=1)

        def total(start: datetime) -> float:
            return round(self.readings.sum_valid(sensor_type_id=volume_type.id, date_from=start, date_to=end), 3)

        return VolumeTotals(
            today_liters=total(start_today),
            last_7_days_liters=total(start_today - timedelta(days=6)),
            month_liters=total(start_month),
        )

    def series(
        self,
        *,
        sensor_type_code: str,
        bucket: str,
        date_from: datetime | None,
        date_to: datetime | None,
        device_id: int | None = None,
        sensor_id: int | None = None,
        fog_collector_id: int | None = None,
    ) -> Series:
        sensor_type = self.sensor_types.get_by(code=sensor_type_code)
        if sensor_type is None:
            raise NotFoundError("Tipo de sensor no encontrado.")
        date_to = date_to or utcnow()
        date_from = date_from or date_to - timedelta(days=7)
        if date_from >= date_to:
            raise BusinessRuleError("La fecha inicial debe ser anterior a la final.", code="rango_invalido")
        if (date_to - date_from) / _BUCKET_SIZES[bucket] > MAX_SERIES_POINTS:
            raise BusinessRuleError(
                "El rango solicitado genera demasiados puntos; use un intervalo mayor.", code="rango_muy_amplio"
            )
        rows = self.readings.aggregate_series(
            sensor_type_id=sensor_type.id,
            bucket=bucket,
            aggregation=sensor_type.aggregation,
            date_from=date_from,
            date_to=date_to,
            timezone=self.settings.local_timezone,
            device_id=device_id,
            sensor_id=sensor_id,
            fog_collector_id=fog_collector_id,
        )
        points = [
            SeriesPoint(
                bucket=row["bucket"].replace(tzinfo=self.tz),
                value=round(float(row["value"]), 3) if row["value"] is not None else None,
                min=row["min"],
                max=row["max"],
                count=row["count"],
            )
            for row in rows
        ]
        return Series(sensor_type=sensor_type, bucket=bucket, date_from=date_from, date_to=date_to, points=points)
