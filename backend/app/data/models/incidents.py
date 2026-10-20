"""Reportes de incidencia (solicitudes de mantenimiento) y notificaciones internas."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data.database import Base, TimestampMixin
from app.data.models.iot import Device, Sensor
from app.data.models.security import User

if TYPE_CHECKING:
    from app.data.models.inventory import MaintenanceRecord

INCIDENT_PRIORITIES = ("baja", "media", "alta")


class IncidentReport(Base, TimestampMixin):
    """Situación reportada por un docente. Su estado se deriva del mantenimiento que la atiende:
    sin mantenimiento está `abierto`; luego sigue el estado del mantenimiento asociado."""

    __tablename__ = "incident_reports"
    __table_args__ = (CheckConstraint(f"priority IN {INCIDENT_PRIORITIES}", name="priority"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    reported_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(10), default="media")
    location_reference: Mapped[str | None] = mapped_column(String(200))
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"), index=True)
    sensor_id: Mapped[int | None] = mapped_column(ForeignKey("sensors.id"))

    reporter: Mapped[User] = relationship(lazy="joined")
    device: Mapped[Device | None] = relationship(lazy="joined")
    sensor: Mapped[Sensor | None] = relationship(lazy="joined")
    maintenance: Mapped["MaintenanceRecord | None"] = relationship(
        lazy="joined", back_populates="incident_report", uselist=False
    )

    @property
    def status(self) -> str:
        return self.maintenance.status if self.maintenance else "abierto"


class Notification(Base):
    """Aviso interno para un usuario (sin canales externos). Se marca como leído, no se elimina."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(150))
    message: Mapped[str] = mapped_column(String(500))
    incident_report_id: Mapped[int | None] = mapped_column(ForeignKey("incident_reports.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
