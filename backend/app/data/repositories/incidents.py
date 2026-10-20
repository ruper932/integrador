"""Repositorios de reportes de incidencia y notificaciones."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import case, func, or_, select, update

from app.data.models.incidents import IncidentReport, Notification
from app.data.models.inventory import MaintenanceRecord
from app.data.repositories.base import Repository

INCIDENT_OPEN = "abierto"
# Clave arbitraria y fija del bloqueo consultivo de PostgreSQL para la detección automática.
AUTO_DETECTION_LOCK = 72_014_001


class IncidentReportRepository(Repository[IncidentReport]):
    model = IncidentReport

    def _filters(
        self,
        *,
        reported_by_id: int | None,
        assigned_to_id: int | None,
        status: str | None,
        priority: str | None = None,
        device_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[Any]:
        filters: list[Any] = []
        if priority:
            filters.append(IncidentReport.priority == priority)
        if device_id is not None:
            filters.append(IncidentReport.device_id == device_id)
        if date_from:
            filters.append(IncidentReport.created_at >= date_from)
        if date_to:
            filters.append(IncidentReport.created_at <= date_to)
        if reported_by_id is not None:
            filters.append(IncidentReport.reported_by_id == reported_by_id)
        if assigned_to_id is not None:
            filters.append(MaintenanceRecord.user_id == assigned_to_id)
        if status == INCIDENT_OPEN:
            filters.append(MaintenanceRecord.id.is_(None))
        elif status:
            filters.append(MaintenanceRecord.status == status)
        return filters

    def search(
        self,
        *,
        offset: int,
        limit: int,
        reported_by_id: int | None = None,
        assigned_to_id: int | None = None,
        status: str | None = None,
        priority_first: bool = False,
        priority: str | None = None,
        device_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[Sequence[IncidentReport], int]:
        stmt = select(IncidentReport).outerjoin(
            MaintenanceRecord, MaintenanceRecord.incident_report_id == IncidentReport.id
        )
        if priority_first:
            # Bandeja de atención: primero lo urgente y, a igual prioridad, lo más antiguo.
            rank = case({"alta": 0, "media": 1, "baja": 2}, value=IncidentReport.priority)
            stmt = stmt.order_by(rank, IncidentReport.created_at, IncidentReport.id)
        else:
            stmt = stmt.order_by(IncidentReport.created_at.desc(), IncidentReport.id.desc())
        filters = self._filters(
            reported_by_id=reported_by_id,
            assigned_to_id=assigned_to_id,
            status=status,
            priority=priority,
            device_id=device_id,
            date_from=date_from,
            date_to=date_to,
        )
        return self.paginate(stmt.where(*filters), offset=offset, limit=limit)

    def lock_auto_detection(self) -> None:
        """Bloqueo de transacción: serializa la detección automática entre procesos de la API."""
        self.session.execute(select(func.pg_advisory_xact_lock(AUTO_DETECTION_LOCK)))

    def has_pending_auto(self, *, device_id: int, cause: str, sensor_id: int | None, finished_since: datetime) -> bool:
        """¿Hay un reporte automático de la misma causa sin finalizar, o finalizado hace poco?
        Evita duplicar reportes mientras el problema se atiende o recién se dio por resuelto."""
        stmt = (
            select(IncidentReport.id)
            .outerjoin(MaintenanceRecord, MaintenanceRecord.incident_report_id == IncidentReport.id)
            .where(
                IncidentReport.source == "sistema",
                IncidentReport.auto_cause == cause,
                IncidentReport.device_id == device_id,
                IncidentReport.sensor_id.is_(None) if sensor_id is None else IncidentReport.sensor_id == sensor_id,
                or_(
                    MaintenanceRecord.id.is_(None),
                    MaintenanceRecord.status != "finalizado",
                    MaintenanceRecord.finished_at >= finished_since,
                ),
            )
            .limit(1)
        )
        return self.session.scalar(stmt) is not None

    def count_by_status(
        self, *, reported_by_id: int | None = None, assigned_to_id: int | None = None
    ) -> dict[str, int]:
        status = func.coalesce(MaintenanceRecord.status, INCIDENT_OPEN)
        stmt = (
            select(status, func.count(IncidentReport.id))
            .select_from(IncidentReport)
            .outerjoin(MaintenanceRecord, MaintenanceRecord.incident_report_id == IncidentReport.id)
            .where(*self._filters(reported_by_id=reported_by_id, assigned_to_id=assigned_to_id, status=None))
            .group_by(status)
        )
        return {row[0]: row[1] for row in self.session.execute(stmt).all()}


class NotificationRepository(Repository[Notification]):
    model = Notification

    def list_for_user(self, user_id: int, *, limit: int, unread_only: bool) -> Sequence[Notification]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        stmt = stmt.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit)
        return self.session.scalars(stmt).all()

    def count_unread(self, user_id: int) -> int:
        stmt = select(func.count()).where(Notification.user_id == user_id, Notification.read_at.is_(None))
        return self.session.scalar(stmt) or 0

    def mark_read(self, user_id: int, now: datetime, *, notification_id: int | None = None) -> int:
        stmt = update(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None))
        if notification_id is not None:
            stmt = stmt.where(Notification.id == notification_id)
        return self.session.execute(stmt.values(read_at=now)).rowcount  # type: ignore[attr-defined]
