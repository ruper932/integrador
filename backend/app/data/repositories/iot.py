"""Repositorios de infraestructura física, dispositivos, sensores y lecturas."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import distinct_on

from app.data.models.infrastructure import FogCollector, Greenhouse, Location, Tank
from app.data.models.iot import (
    Device,
    DeviceCredential,
    DeviceLocation,
    MeasurementBatch,
    Sensor,
    SensorCalibration,
    SensorReading,
    SensorType,
)
from app.data.repositories.base import Repository

SERIES_BUCKETS = ("hour", "day", "week", "month")


class LocationRepository(Repository[Location]):
    model = Location


class FogCollectorRepository(Repository[FogCollector]):
    model = FogCollector


class TankRepository(Repository[Tank]):
    model = Tank


class GreenhouseRepository(Repository[Greenhouse]):
    model = Greenhouse


class SensorTypeRepository(Repository[SensorType]):
    model = SensorType


class DeviceRepository(Repository[Device]):
    model = Device

    def get_by_code(self, code: str) -> Device | None:
        return self.session.scalars(select(Device).where(Device.code == code)).first()


class DeviceCredentialRepository(Repository[DeviceCredential]):
    model = DeviceCredential

    def get_active(self, device_id: int, key_hash: str) -> DeviceCredential | None:
        stmt = select(DeviceCredential).where(
            DeviceCredential.device_id == device_id,
            DeviceCredential.key_hash == key_hash,
            DeviceCredential.revoked_at.is_(None),
        )
        return self.session.scalars(stmt).first()

    def list_active(self, device_id: int) -> Sequence[DeviceCredential]:
        stmt = select(DeviceCredential).where(
            DeviceCredential.device_id == device_id, DeviceCredential.revoked_at.is_(None)
        )
        return self.session.scalars(stmt).all()


class DeviceLocationRepository(Repository[DeviceLocation]):
    model = DeviceLocation

    def get_current(self, device_id: int) -> DeviceLocation | None:
        stmt = select(DeviceLocation).where(DeviceLocation.device_id == device_id, DeviceLocation.ended_at.is_(None))
        return self.session.scalars(stmt).first()


class SensorRepository(Repository[Sensor]):
    model = Sensor

    def list_by_device(self, device_id: int) -> Sequence[Sensor]:
        return self.session.scalars(select(Sensor).where(Sensor.device_id == device_id).order_by(Sensor.code)).all()

    def get_by_device_and_code(self, device_id: int, code: str) -> Sensor | None:
        return self.session.scalars(select(Sensor).where(Sensor.device_id == device_id, Sensor.code == code)).first()


class SensorCalibrationRepository(Repository[SensorCalibration]):
    model = SensorCalibration


class MeasurementBatchRepository(Repository[MeasurementBatch]):
    model = MeasurementBatch

    def get_by_uid(self, device_id: int, batch_uid: uuid.UUID) -> MeasurementBatch | None:
        stmt = select(MeasurementBatch).where(
            MeasurementBatch.device_id == device_id, MeasurementBatch.batch_uid == batch_uid
        )
        return self.session.scalars(stmt).first()


class SensorReadingRepository(Repository[SensorReading]):
    model = SensorReading

    def existing_message_uids(self, uids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
        if not uids:
            return set()
        stmt = select(SensorReading.message_uid).where(SensorReading.message_uid.in_(uids))
        return set(self.session.scalars(stmt).all())

    def search(
        self,
        *,
        offset: int,
        limit: int,
        device_id: int | None = None,
        sensor_id: int | None = None,
        sensor_type_code: str | None = None,
        fog_collector_id: int | None = None,
        quality: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[Sequence[SensorReading], int]:
        stmt = select(SensorReading).join(Sensor, Sensor.id == SensorReading.sensor_id)
        filters: list[Any] = []
        if device_id is not None:
            filters.append(SensorReading.device_id == device_id)
        if sensor_id is not None:
            filters.append(SensorReading.sensor_id == sensor_id)
        if sensor_type_code:
            stmt = stmt.join(SensorType, SensorType.id == SensorReading.sensor_type_id)
            filters.append(SensorType.code == sensor_type_code)
        if fog_collector_id is not None:
            filters.append(Sensor.fog_collector_id == fog_collector_id)
        if quality:
            filters.append(SensorReading.quality == quality)
        if date_from:
            filters.append(SensorReading.measured_at >= date_from)
        if date_to:
            filters.append(SensorReading.measured_at <= date_to)
        stmt = stmt.where(*filters).order_by(SensorReading.measured_at.desc(), SensorReading.id.desc())
        return self.paginate(stmt, offset=offset, limit=limit)

    def count_by_device_and_quality(
        self,
        *,
        date_from: datetime,
        date_to: datetime,
        device_id: int | None = None,
        fog_collector_id: int | None = None,
    ) -> list[tuple[str, str, int]]:
        """(código del dispositivo, calidad, cantidad) de las lecturas del periodo."""
        stmt = (
            select(Device.code, SensorReading.quality, func.count())
            .join(Sensor, Sensor.id == SensorReading.sensor_id)
            .join(Device, Device.id == SensorReading.device_id)
            .where(SensorReading.measured_at >= date_from, SensorReading.measured_at <= date_to)
            .group_by(Device.code, SensorReading.quality)
            .order_by(Device.code)
        )
        if device_id is not None:
            stmt = stmt.where(SensorReading.device_id == device_id)
        if fog_collector_id is not None:
            stmt = stmt.where(Sensor.fog_collector_id == fog_collector_id)
        return [(code, quality, count) for code, quality, count in self.session.execute(stmt)]

    def latest_valid_per_sensor(self, device_id: int | None = None) -> Sequence[SensorReading]:
        stmt = (
            select(SensorReading)
            .ext(distinct_on(SensorReading.sensor_id))
            .where(SensorReading.quality == "valida")
            .order_by(SensorReading.sensor_id, SensorReading.measured_at.desc())
        )
        if device_id is not None:
            stmt = stmt.where(SensorReading.device_id == device_id)
        return self.session.scalars(stmt).unique().all()

    def aggregate_series(
        self,
        *,
        sensor_type_id: int,
        bucket: str,
        aggregation: str,
        date_from: datetime,
        date_to: datetime,
        timezone: str,
        device_id: int | None = None,
        sensor_id: int | None = None,
        fog_collector_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Agrega lecturas válidas por intervalo.

        Variables incrementales se suman; variables instantáneas se promedian.
        Los intervalos se calculan en la zona horaria local indicada.
        """
        local_ts = func.timezone(timezone, SensorReading.measured_at)
        if bucket not in SERIES_BUCKETS:
            raise ValueError(f"Intervalo no soportado: {bucket}")
        bucket_col = func.date_trunc(bucket, local_ts).label("bucket")
        value_agg = func.sum(SensorReading.value) if aggregation == "incremental" else func.avg(SensorReading.value)
        stmt = (
            select(
                bucket_col,
                value_agg.label("value"),
                func.min(SensorReading.value).label("min"),
                func.max(SensorReading.value).label("max"),
                func.count().label("count"),
            )
            .join(Sensor, Sensor.id == SensorReading.sensor_id)
            .where(
                SensorReading.sensor_type_id == sensor_type_id,
                SensorReading.quality == "valida",
                SensorReading.measured_at >= date_from,
                SensorReading.measured_at < date_to,
            )
            # Se agrupa por posición para no repetir parámetros enlazados en GROUP BY.
            .group_by(text("1"))
            .order_by(text("1"))
        )
        if device_id is not None:
            stmt = stmt.where(SensorReading.device_id == device_id)
        if sensor_id is not None:
            stmt = stmt.where(SensorReading.sensor_id == sensor_id)
        if fog_collector_id is not None:
            stmt = stmt.where(Sensor.fog_collector_id == fog_collector_id)
        return [dict(row._mapping) for row in self.session.execute(stmt)]

    def sum_valid(self, *, sensor_type_id: int, date_from: datetime, date_to: datetime) -> float:
        stmt = select(func.coalesce(func.sum(SensorReading.value), 0.0)).where(
            SensorReading.sensor_type_id == sensor_type_id,
            SensorReading.quality == "valida",
            SensorReading.measured_at >= date_from,
            SensorReading.measured_at < date_to,
        )
        return float(self.session.scalar(stmt) or 0.0)
