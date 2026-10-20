"""Modelos IoT: dispositivos, credenciales, sensores y lecturas."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data.database import Base, TimestampMixin
from app.data.models.infrastructure import FogCollector, Location, Tank

DEVICE_STATUSES = ("activo", "inactivo", "mantenimiento")
SENSOR_STATUSES = ("activo", "inactivo", "mantenimiento")
# incremental: el valor representa lo ocurrido en el intervalo (p. ej. litros captados desde la lectura anterior).
# instantaneo: el valor representa el estado en el momento de la medición (temperatura, nivel del tanque).
AGGREGATION_KINDS = ("incremental", "instantaneo")
READING_QUALITIES = ("valida", "sin_dato", "fuera_de_rango", "unidad_invalida", "invalida")


class Device(Base, TimestampMixin):
    __tablename__ = "devices"
    __table_args__ = (CheckConstraint(f"status IN {DEVICE_STATUSES}", name="status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    firmware_version: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16), default="activo")
    fog_collector_id: Mapped[int | None] = mapped_column(ForeignKey("fog_collectors.id"))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    fog_collector: Mapped[FogCollector | None] = relationship(lazy="joined")


class DeviceCredential(Base):
    __tablename__ = "device_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    key_prefix: Mapped[str] = mapped_column(String(12))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeviceLocation(Base):
    __tablename__ = "device_locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    location: Mapped[Location] = relationship(lazy="joined")


class SensorType(Base):
    __tablename__ = "sensor_types"
    __table_args__ = (CheckConstraint(f"aggregation IN {AGGREGATION_KINDS}", name="aggregation"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    unit: Mapped[str] = mapped_column(String(16))
    min_value: Mapped[float] = mapped_column(Float)
    max_value: Mapped[float] = mapped_column(Float)
    aggregation: Mapped[str] = mapped_column(String(16))
    description: Mapped[str | None] = mapped_column(Text)


class Sensor(Base, TimestampMixin):
    __tablename__ = "sensors"
    __table_args__ = (
        UniqueConstraint("device_id", "code", name="uq_sensors_device_code"),
        CheckConstraint(f"status IN {SENSOR_STATUSES}", name="status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    sensor_type_id: Mapped[int] = mapped_column(ForeignKey("sensor_types.id"))
    code: Mapped[str] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16), default="activo")
    fog_collector_id: Mapped[int | None] = mapped_column(ForeignKey("fog_collectors.id"))
    tank_id: Mapped[int | None] = mapped_column(ForeignKey("tanks.id"))

    device: Mapped[Device] = relationship(lazy="joined")
    sensor_type: Mapped[SensorType] = relationship(lazy="joined")
    fog_collector: Mapped[FogCollector | None] = relationship(lazy="joined")
    tank: Mapped[Tank | None] = relationship(lazy="joined")


class SensorCalibration(Base):
    __tablename__ = "sensor_calibrations"

    id: Mapped[int] = mapped_column(primary_key=True)
    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensors.id"), index=True)
    calibrated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    offset_value: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=0)
    scale_factor: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=1)
    notes: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MeasurementBatch(Base):
    __tablename__ = "measurement_batches"
    __table_args__ = (UniqueConstraint("device_id", "batch_uid", name="uq_measurement_batches_device_batch"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    batch_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    readings_count: Mapped[int] = mapped_column(Integer, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0)
    invalid_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)


class SensorReading(Base):
    __tablename__ = "sensor_readings"
    __table_args__ = (
        CheckConstraint(f"quality IN {READING_QUALITIES}", name="quality"),
        # Una lectura válida siempre tiene valor; una lectura sin dato nunca lo tiene.
        CheckConstraint("quality <> 'valida' OR value IS NOT NULL", name="valid_has_value"),
        CheckConstraint("quality <> 'sin_dato' OR value IS NULL", name="no_data_is_null"),
        Index("ix_sensor_readings_sensor_measured", "sensor_id", "measured_at"),
        Index("ix_sensor_readings_type_measured", "sensor_type_id", "measured_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    message_uid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), unique=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("measurement_batches.id"), index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"))
    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensors.id"))
    sensor_type_id: Mapped[int] = mapped_column(ForeignKey("sensor_types.id"))
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    value: Mapped[float | None] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(16))
    quality: Mapped[str] = mapped_column(String(20))
    quality_detail: Mapped[str | None] = mapped_column(String(255))

    sensor: Mapped[Sensor] = relationship(lazy="joined")
