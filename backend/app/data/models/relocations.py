"""Solicitudes de reubicación de atrapanieblas (por problemas de espacio u otros motivos)."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data.database import Base, TimestampMixin
from app.data.models.infrastructure import FogCollector, Location
from app.data.models.security import User

RELOCATION_STATUSES = ("pendiente", "aceptado", "en_progreso", "finalizado", "rechazado")
RELOCATION_ACTIVE_STATUSES = ("pendiente", "aceptado", "en_progreso")
RELOCATION_REASONS = ("espacio_insuficiente", "interferencia_con_actividades", "obstruccion_de_la_niebla", "otro")


class FogCollectorRelocation(Base, TimestampMixin):
    """Un docente solicita mover un atrapanieblas; el personal de mantenimiento la acepta, la ejecuta
    y la finaliza indicando la nueva ubicación (o la rechaza con un motivo). La ubicación de origen
    se guarda al solicitar para conservar la trazabilidad del movimiento."""

    __tablename__ = "fog_collector_relocations"
    __table_args__ = (
        CheckConstraint(f"status IN {RELOCATION_STATUSES}", name="status"),
        CheckConstraint(f"reason IN {RELOCATION_REASONS}", name="reason"),
        CheckConstraint("status = 'pendiente' OR status = 'rechazado' OR assigned_to_id IS NOT NULL", name="asignada"),
        CheckConstraint(
            "status <> 'finalizado' OR (destination_location_id IS NOT NULL AND work_notes IS NOT NULL"
            " AND finished_at IS NOT NULL)",
            name="finalizada_completa",
        ),
        CheckConstraint("status <> 'rechazado' OR rejection_reason IS NOT NULL", name="rechazo_motivado"),
        # Un atrapanieblas solo puede tener una solicitud en curso (evita dos traslados simultáneos).
        Index(
            "uq_fog_collector_relocations_activa",
            "fog_collector_id",
            unique=True,
            postgresql_where=text("status IN ('pendiente', 'aceptado', 'en_progreso')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fog_collector_id: Mapped[int] = mapped_column(ForeignKey("fog_collectors.id"), index=True)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    reason: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text)
    origin_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    proposed_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    proposed_place: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(15), default="pendiente", server_default="pendiente")
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    destination_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    previous_orientation: Mapped[str | None] = mapped_column(String(40))
    new_orientation: Mapped[str | None] = mapped_column(String(40))
    work_notes: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    fog_collector: Mapped[FogCollector] = relationship(lazy="joined")
    requester: Mapped[User] = relationship(foreign_keys=[requested_by_id], lazy="joined")
    assignee: Mapped[User | None] = relationship(foreign_keys=[assigned_to_id], lazy="joined")
    origin_location: Mapped[Location | None] = relationship(foreign_keys=[origin_location_id], lazy="joined")
    proposed_location: Mapped[Location | None] = relationship(foreign_keys=[proposed_location_id], lazy="joined")
    destination_location: Mapped[Location | None] = relationship(foreign_keys=[destination_location_id], lazy="joined")
