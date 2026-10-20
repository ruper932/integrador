"""Modelos de inventario de repuestos IoT y mantenimiento."""

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data.database import Base, TimestampMixin
from app.data.models.iot import Device, Sensor
from app.data.models.security import User

if TYPE_CHECKING:
    from app.data.models.incidents import IncidentReport

ITEM_CONDITIONS = ("nuevo", "usado", "reacondicionado", "en_revision", "danado")
MAINTENANCE_TYPES = ("preventivo", "correctivo", "reemplazo", "calibracion", "limpieza", "inspeccion")
COMPONENT_FINAL_STATUSES = ("operativo", "operativo_con_observaciones", "fuera_de_servicio", "reemplazado")
PERIOD_STATUSES = ("abierto", "cerrado")
MAINTENANCE_ACCEPTED = "aceptado"
MAINTENANCE_IN_PROGRESS = "en_progreso"
MAINTENANCE_FINISHED = "finalizado"
MAINTENANCE_STATUSES = (MAINTENANCE_ACCEPTED, MAINTENANCE_IN_PROGRESS, MAINTENANCE_FINISHED)


class InventoryCategory(Base, TimestampMixin):
    __tablename__ = "inventory_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class InventoryItem(Base, TimestampMixin):
    __tablename__ = "inventory_items"
    __table_args__ = (
        CheckConstraint("current_stock >= 0", name="stock_non_negative"),
        CheckConstraint("min_stock >= 0", name="min_stock_non_negative"),
        CheckConstraint(f"condition IN {ITEM_CONDITIONS}", name="condition"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[int] = mapped_column(ForeignKey("inventory_categories.id"))
    unit: Mapped[str] = mapped_column(String(20))
    current_stock: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)
    min_stock: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=0)
    condition: Mapped[str] = mapped_column(String(20), default="nuevo")
    storage_location: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    category: Mapped[InventoryCategory] = relationship(lazy="joined")
    compatibilities: Mapped[list["InventoryItemCompatibility"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )


class InventoryItemCompatibility(Base):
    __tablename__ = "inventory_item_compatibility"
    __table_args__ = (
        CheckConstraint("num_nonnulls(device_id, sensor_id) = 1", name="one_target"),
        UniqueConstraint("item_id", "device_id", "sensor_id", name="uq_inventory_item_compatibility_target"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"))
    sensor_id: Mapped[int | None] = mapped_column(ForeignKey("sensors.id"))

    device: Mapped[Device | None] = relationship(lazy="joined")
    sensor: Mapped[Sensor | None] = relationship(lazy="joined")


class InventoryMovementType(Base):
    __tablename__ = "inventory_movement_types"
    __table_args__ = (CheckConstraint("direction IN (1, -1)", name="direction"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    direction: Mapped[int] = mapped_column(SmallInteger)
    manual_allowed: Mapped[bool] = mapped_column(Boolean, default=True)


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_cost IS NULL OR unit_cost >= 0", name="unit_cost_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"), index=True)
    movement_type_id: Mapped[int] = mapped_column(ForeignKey("inventory_movement_types.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    stock_before: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    stock_after: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    reason: Mapped[str] = mapped_column(String(255))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    maintenance_record_id: Mapped[int | None] = mapped_column(ForeignKey("maintenance_records.id"))
    # Costo unitario en bolivianos (Bs); se registra en las entradas para valorizar el inventario.
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    # Fecha efectiva del movimiento (los ajustes de cierre se fechan al final del periodo).
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    # Fecha en que se registró en el sistema.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    movement_type: Mapped[InventoryMovementType] = relationship(lazy="joined")
    user: Mapped[User] = relationship(lazy="joined")
    item: Mapped[InventoryItem] = relationship(lazy="joined")


class MaintenanceRecord(Base):
    """Mantenimiento de un dispositivo o sensor.

    Si atiende un reporte de incidencia pasa por `aceptado` → `en_progreso` → `finalizado`; los
    detalles del trabajo (dispositivo, tipo, descripción, estado final) se completan al finalizar.
    Un registro directo se crea ya `finalizado`.
    """

    __tablename__ = "maintenance_records"
    __table_args__ = (
        CheckConstraint(f"maintenance_type IN {MAINTENANCE_TYPES}", name="maintenance_type"),
        CheckConstraint(f"final_status IN {COMPONENT_FINAL_STATUSES}", name="final_status"),
        CheckConstraint(f"status IN {MAINTENANCE_STATUSES}", name="status"),
        CheckConstraint(
            "status <> 'finalizado' OR (device_id IS NOT NULL AND performed_at IS NOT NULL"
            " AND maintenance_type IS NOT NULL AND description IS NOT NULL AND final_status IS NOT NULL)",
            name="finalizado_completo",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(15), default=MAINTENANCE_FINISHED, server_default=MAINTENANCE_FINISHED)
    incident_report_id: Mapped[int | None] = mapped_column(ForeignKey("incident_reports.id"), unique=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"), index=True)
    sensor_id: Mapped[int | None] = mapped_column(ForeignKey("sensors.id"), index=True)
    performed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Responsable: quien registra el mantenimiento o acepta el reporte.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    maintenance_type: Mapped[str | None] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(Text)
    final_status: Mapped[str | None] = mapped_column(String(30))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    device: Mapped[Device | None] = relationship(lazy="joined")
    sensor: Mapped[Sensor | None] = relationship(lazy="joined")
    user: Mapped[User] = relationship(lazy="joined")
    items: Mapped[list["MaintenanceItem"]] = relationship(lazy="selectin", back_populates="record")
    incident_report: Mapped["IncidentReport | None"] = relationship(back_populates="maintenance")


class MaintenanceItem(Base):
    __tablename__ = "maintenance_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="quantity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    maintenance_record_id: Mapped[int] = mapped_column(ForeignKey("maintenance_records.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    movement_id: Mapped[int] = mapped_column(ForeignKey("inventory_movements.id"), unique=True)

    record: Mapped[MaintenanceRecord] = relationship(back_populates="items")
    item: Mapped[InventoryItem] = relationship(lazy="joined")


class InventoryPeriod(Base):
    """Periodo del sistema de inventario periódico (mes, trimestre o gestión)."""

    __tablename__ = "inventory_periods"
    __table_args__ = (
        CheckConstraint("start_date <= end_date", name="date_range"),
        CheckConstraint(f"status IN {PERIOD_STATUSES}", name="status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="abierto")
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    closed_by: Mapped[User | None] = relationship(foreign_keys=[closed_by_id], lazy="joined")


class InventoryCount(Base):
    """Conteo físico de un repuesto al cierre de un periodo."""

    __tablename__ = "inventory_counts"
    __table_args__ = (
        UniqueConstraint("period_id", "item_id", name="uq_inventory_counts_period_item"),
        CheckConstraint("counted_quantity >= 0", name="counted_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("inventory_periods.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"))
    counted_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    # Se fijan al cerrar el periodo (saldo según registros al final del periodo y diferencia).
    theoretical_quantity: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    difference: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    notes: Mapped[str | None] = mapped_column(String(255))
    counted_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    counted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped[InventoryItem] = relationship(lazy="joined")
    counted_by: Mapped[User] = relationship(lazy="joined")


class InventoryPeriodBalance(Base):
    """Saldos congelados de cada repuesto al cerrar un periodo (no se recalculan)."""

    __tablename__ = "inventory_period_balances"

    period_id: Mapped[int] = mapped_column(ForeignKey("inventory_periods.id"), primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"), primary_key=True)
    opening_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    entries_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    exits_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    maintenance_exits_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    adjustments_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    closing_quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    opening_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    entries_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    average_unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    closing_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    item: Mapped[InventoryItem] = relationship(lazy="joined")
