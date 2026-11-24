"""Consulta de históricos y datos del dashboard."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.business.rules.connection import is_stale
from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.errors import BusinessRuleError, NotFoundError
from app.data.models.iot import Device, SensorReading, SensorType
from app.data.repositories.iot import (
    DeviceRepository,
    SensorReadingRepository,
    SensorRepository,
    SensorTypeRepository,
)

VOLUME_TYPE_CODE = "volumen_captado"
MAX_SERIES_POINTS = 5000
LIVE_MAX_MINUTES = 360  # 6 h a 5 s son 4320 puntos por variable: suficiente para el panel en vivo


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


@dataclass(frozen=True)
class LiveVariable:
    sensor_type: SensorType
    points: list[tuple[datetime, float]]
    latest_value: float | None
    latest_at: datetime | None

    def _values(self) -> list[float]:
        return [v for _, v in self.points]

    @property
    def minimum(self) -> float | None:
        return min(self._values(), default=None)

    @property
    def maximum(self) -> float | None:
        return max(self._values(), default=None)

    @property
    def average(self) -> float | None:
        values = self._values()
        return sum(values) / len(values) if values else None


@dataclass(frozen=True)
class LiveSnapshot:
    generated_at: datetime
    window_minutes: int
    device: Device
    is_stale: bool
    variables: list[LiveVariable]


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
        self.sensors = SensorRepository(session)
        self.settings = get_settings()
        self.tz = ZoneInfo(self.settings.local_timezone)

    def search(self, **filters: object) -> tuple[Sequence[SensorReading], int]:
        date_from, date_to = filters.get("date_from"), filters.get("date_to")
        if isinstance(date_from, datetime) and isinstance(date_to, datetime) and date_from > date_to:
            raise BusinessRuleError("La fecha inicial debe ser anterior a la final.", code="rango_invalido")
        return self.readings.search(**filters)  # type: ignore[arg-type]

    @staticmethod
    def _is_stale(ts: datetime | None, device: Device, now: datetime) -> bool:
        return is_stale(ts, device.sample_interval_s, now)

    def live(self, device_id: int, minutes: int) -> LiveSnapshot:
        """Lecturas válidas recientes de una estación, por variable, para el panel de monitoreo en vivo.

        El último valor se toma aunque sea anterior a la ventana (el panel lo marca como desactualizado);
        las variables de los sensores inactivos no se muestran.
        """
        if not 1 <= minutes <= LIVE_MAX_MINUTES:
            raise BusinessRuleError(
                f"La ventana debe estar entre 1 y {LIVE_MAX_MINUTES} minutos.", code="ventana_invalida"
            )
        device = self.devices.get(device_id)
        if device is None:
            raise NotFoundError("Dispositivo no encontrado.")
        now = utcnow()
        sensors = [s for s in self.sensors.list_by_device(device_id) if s.status == "activo"]
        types: dict[int, SensorType] = {}
        for sensor in sorted(sensors, key=lambda s: s.sensor_type.code):
            types.setdefault(sensor.sensor_type_id, sensor.sensor_type)
        points: dict[int, list[tuple[datetime, float]]] = {type_id: [] for type_id in types}
        for type_id, measured_at, value in self.readings.valid_points(device_id, now - timedelta(minutes=minutes), now):
            if type_id in points:
                points[type_id].append((measured_at, value))
        latest: dict[int, SensorReading] = {}
        for reading in self.readings.latest_valid_per_sensor(device_id):
            current = latest.get(reading.sensor_type_id)
            if current is None or reading.measured_at > current.measured_at:
                latest[reading.sensor_type_id] = reading
        variables = [
            LiveVariable(
                sensor_type=sensor_type,
                points=points[type_id],
                latest_value=float(latest[type_id].value) if type_id in latest else None,
                latest_at=latest[type_id].measured_at if type_id in latest else None,
            )
            for type_id, sensor_type in types.items()
        ]
        return LiveSnapshot(
            generated_at=now,
            window_minutes=minutes,
            device=device,
            is_stale=self._is_stale(device.last_seen_at, device, now),
            variables=variables,
        )

    def summary(self) -> DashboardSummary:
        now = utcnow()
        devices = [d for d in self.devices.list(limit=1000, order_by=Device.code) if d.status != "inactivo"]
        statuses = [
            DeviceStatus(
                device=d,
                is_stale=self._is_stale(d.last_seen_at, d, now),
                minutes_since_last_seen=int((now - d.last_seen_at).total_seconds() // 60) if d.last_seen_at else None,
            )
            for d in devices
        ]
        by_id = {d.id: d for d in devices}
        latest = [
            LatestValue(reading=r, is_stale=self._is_stale(r.measured_at, by_id[r.device_id], now))
            for r in self.readings.latest_valid_per_sensor()
            if r.device_id in by_id and r.sensor.status == "activo"
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
