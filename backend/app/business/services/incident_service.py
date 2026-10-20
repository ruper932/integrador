"""Reportes de incidencia y su atención mediante mantenimientos.

Flujo: un docente reporta una situación (`abierto`) → el personal de mantenimiento recibe un aviso
y acepta el reporte, lo que crea el mantenimiento (`aceptado`) → lo inicia (`en_progreso`) → lo
finaliza registrando el trabajo y los repuestos (`finalizado`), que se descuentan del inventario.
El docente recibe un aviso en cada etapa; el administrador y el director ven todo el proceso.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.business.services.audit_service import AuditService
from app.business.services.context import RequestContext
from app.business.services.maintenance_service import MaintenanceService, UsedPart
from app.business.services.notification_service import NotificationService
from app.core.clock import utcnow
from app.core.errors import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.core.permissions import Permission
from app.data.models.incidents import IncidentReport
from app.data.models.inventory import (
    MAINTENANCE_ACCEPTED,
    MAINTENANCE_FINISHED,
    MAINTENANCE_IN_PROGRESS,
    MaintenanceRecord,
)
from app.data.models.security import User
from app.data.repositories.incidents import INCIDENT_OPEN, IncidentReportRepository
from app.data.repositories.inventory import MaintenanceRecordRepository
from app.data.repositories.security import UserRepository

Scope = Literal["mine", "open", "assigned", "all"]
INCIDENT_STATUSES = (INCIDENT_OPEN, MAINTENANCE_ACCEPTED, MAINTENANCE_IN_PROGRESS, MAINTENANCE_FINISHED)
FINAL_STATUS_LABELS = {
    "operativo": "operativo",
    "operativo_con_observaciones": "operativo con observaciones",
    "fuera_de_servicio": "fuera de servicio",
    "reemplazado": "reemplazado",
}

# Permiso que exige cada vista de la lista de reportes.
SCOPE_PERMISSION: dict[Scope, Permission] = {
    "mine": Permission.INCIDENTS_REPORT,
    "open": Permission.INCIDENTS_ATTEND,
    "assigned": Permission.INCIDENTS_ATTEND,
    "all": Permission.INCIDENTS_SUPERVISE,
}


@dataclass(frozen=True)
class IncidentSummary:
    """Conteos por estado de los reportes que el usuario puede ver."""

    mine: dict[str, int] | None
    open: int | None
    assigned_active: int | None
    all: dict[str, int] | None


def _has(user: User, permission: Permission) -> bool:
    return permission.value in user.permission_codes


def _require_user(ctx: RequestContext) -> User:
    if ctx.user is None:
        raise ForbiddenError("Operación no permitida.")
    return ctx.user


class IncidentService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.reports = IncidentReportRepository(session)
        self.records = MaintenanceRecordRepository(session)
        self.users = UserRepository(session)
        self.maintenance = MaintenanceService(session)
        self.notifications = NotificationService(session)
        self.audit = AuditService(session)

    # --- Consulta -------------------------------------------------------------

    def search(
        self, ctx: RequestContext, *, scope: Scope, status: str | None, offset: int, limit: int
    ) -> tuple[Sequence[IncidentReport], int]:
        user = _require_user(ctx)
        if not _has(user, SCOPE_PERMISSION[scope]):
            raise ForbiddenError("No tiene permiso para consultar estos reportes.")
        if scope == "mine":
            return self.reports.search(offset=offset, limit=limit, reported_by_id=user.id, status=status)
        if scope == "open":
            return self.reports.search(offset=offset, limit=limit, status=INCIDENT_OPEN, priority_first=True)
        if scope == "assigned":
            return self.reports.search(offset=offset, limit=limit, assigned_to_id=user.id, status=status)
        return self.reports.search(offset=offset, limit=limit, status=status)

    def get(self, ctx: RequestContext, report_id: int) -> IncidentReport:
        user = _require_user(ctx)
        report = self.reports.get(report_id)
        visible = report is not None and (
            report.reported_by_id == user.id
            or _has(user, Permission.INCIDENTS_SUPERVISE)
            or _has(user, Permission.INCIDENTS_ATTEND)
        )
        # Un reporte ajeno se informa como inexistente para no revelar su existencia.
        if report is None or not visible:
            raise NotFoundError("Reporte no encontrado.")
        return report

    def summary(self, ctx: RequestContext) -> IncidentSummary:
        user = _require_user(ctx)
        attend = _has(user, Permission.INCIDENTS_ATTEND)
        assigned = self.reports.count_by_status(assigned_to_id=user.id) if attend else {}
        return IncidentSummary(
            mine=self.reports.count_by_status(reported_by_id=user.id)
            if _has(user, Permission.INCIDENTS_REPORT)
            else None,
            open=self.reports.count_by_status().get(INCIDENT_OPEN, 0) if attend else None,
            assigned_active=assigned.get(MAINTENANCE_ACCEPTED, 0) + assigned.get(MAINTENANCE_IN_PROGRESS, 0)
            if attend
            else None,
            all=self.reports.count_by_status() if _has(user, Permission.INCIDENTS_SUPERVISE) else None,
        )

    # --- Reporte ----------------------------------------------------------------

    def report(
        self,
        ctx: RequestContext,
        *,
        title: str,
        description: str,
        priority: str,
        location_reference: str | None,
        device_id: int | None,
        sensor_id: int | None,
    ) -> IncidentReport:
        user = _require_user(ctx)
        if sensor_id is not None and device_id is None:
            raise BusinessRuleError("Indique el dispositivo al que pertenece el sensor.", code="dispositivo_requerido")
        if device_id is not None:
            self.maintenance.validate_target(device_id, sensor_id)
        report = self.reports.add(
            IncidentReport(
                reported_by_id=user.id,
                title=title,
                description=description,
                priority=priority,
                location_reference=location_reference,
                device_id=device_id,
                sensor_id=sensor_id,
            )
        )
        attenders = [u.id for u in self.users.active_with_permission(Permission.INCIDENTS_ATTEND) if u.id != user.id]
        self.notifications.notify(
            attenders,
            "Nuevo reporte de incidencia",
            f"{user.full_name} reportó «{title}» (prioridad {priority}).",
            incident_report_id=report.id,
        )
        self.audit.record(
            ctx,
            "incidencia.reportar",
            entity_type="incident_report",
            entity_id=report.id,
            details={"prioridad": priority, "device_id": device_id, "sensor_id": sensor_id},
        )
        self.session.commit()
        self.session.refresh(report)
        return report

    # --- Atención ------------------------------------------------------------------

    def accept(self, ctx: RequestContext, report_id: int) -> IncidentReport:
        user = _require_user(ctx)
        # El bloqueo evita que dos técnicos acepten el mismo reporte a la vez.
        report = self.reports.get_for_update(report_id)
        if report is None:
            raise NotFoundError("Reporte no encontrado.")
        if report.maintenance is not None:
            raise ConflictError(
                f"El reporte ya fue aceptado por {report.maintenance.user.full_name}.", code="reporte_ya_aceptado"
            )
        now = utcnow()
        record = self.records.add(
            MaintenanceRecord(
                status=MAINTENANCE_ACCEPTED,
                incident_report_id=report.id,
                device_id=report.device_id,
                sensor_id=report.sensor_id,
                user_id=user.id,
                accepted_at=now,
            )
        )
        self._notify_reporter(
            report, "Su reporte fue aceptado", f"{user.full_name} aceptó su reporte «{report.title}»."
        )
        self.audit.record(
            ctx,
            "incidencia.aceptar",
            entity_type="incident_report",
            entity_id=report.id,
            details={"maintenance_record_id": record.id},
        )
        return self._commit(report)

    def start(self, ctx: RequestContext, report_id: int) -> IncidentReport:
        user = _require_user(ctx)
        report, record = self._assigned(user, report_id)
        if record.status != MAINTENANCE_ACCEPTED:
            raise BusinessRuleError("Solo se puede iniciar un mantenimiento aceptado.", code="transicion_invalida")
        record.status = MAINTENANCE_IN_PROGRESS
        record.started_at = utcnow()
        self._notify_reporter(
            report,
            "Mantenimiento en progreso",
            f"{user.full_name} inició el mantenimiento de su reporte «{report.title}».",
        )
        self.audit.record(
            ctx,
            "incidencia.iniciar",
            entity_type="incident_report",
            entity_id=report.id,
            details={"maintenance_record_id": record.id},
        )
        return self._commit(report)

    def finish(
        self,
        ctx: RequestContext,
        report_id: int,
        *,
        device_id: int | None,
        sensor_id: int | None,
        maintenance_type: str,
        description: str,
        final_status: str,
        parts: Sequence[UsedPart],
    ) -> IncidentReport:
        user = _require_user(ctx)
        report, record = self._assigned(user, report_id)
        if record.status != MAINTENANCE_IN_PROGRESS:
            raise BusinessRuleError("Solo se puede finalizar un mantenimiento en progreso.", code="transicion_invalida")
        device_id = device_id if device_id is not None else record.device_id
        if device_id is None:
            raise BusinessRuleError("Indique el dispositivo atendido.", code="dispositivo_requerido")
        self.maintenance.validate_target(device_id, sensor_id)
        self.maintenance.validate_work(maintenance_type, parts)

        now = utcnow()
        record.device_id = device_id
        record.sensor_id = sensor_id
        record.maintenance_type = maintenance_type
        record.description = description
        record.final_status = final_status
        record.performed_at = now
        record.finished_at = now
        record.status = MAINTENANCE_FINISHED
        self.session.flush()
        # Si algún repuesto no tiene stock suficiente, la transacción completa se revierte.
        self.maintenance.consume_parts(ctx, record, parts)
        self._notify_reporter(
            report,
            "Su reporte fue atendido",
            f"{user.full_name} finalizó el mantenimiento de «{report.title}». "
            f"Estado del componente: {FINAL_STATUS_LABELS.get(final_status, final_status)}.",
        )
        self.audit.record(
            ctx,
            "incidencia.finalizar",
            entity_type="incident_report",
            entity_id=report.id,
            details={"maintenance_record_id": record.id, "device_id": device_id, "repuestos": len(parts)},
        )
        return self._commit(report)

    # --- Auxiliares ------------------------------------------------------------------

    def _assigned(self, user: User, report_id: int) -> tuple[IncidentReport, MaintenanceRecord]:
        report = self.reports.get_for_update(report_id)
        if report is None:
            raise NotFoundError("Reporte no encontrado.")
        record = report.maintenance
        if record is None:
            raise BusinessRuleError("El reporte todavía no fue aceptado.", code="transicion_invalida")
        if record.user_id != user.id:
            raise ForbiddenError("Solo el personal asignado puede actualizar este mantenimiento.")
        # Bloquea también el mantenimiento: dos solicitudes simultáneas no avanzan el mismo estado.
        locked = self.records.get_for_update(record.id)
        if locked is None:
            raise NotFoundError("Mantenimiento no encontrado.")
        return report, locked

    def _notify_reporter(self, report: IncidentReport, title: str, message: str) -> None:
        self.notifications.notify([report.reported_by_id], title, message, incident_report_id=report.id)

    def _commit(self, report: IncidentReport) -> IncidentReport:
        self.session.commit()
        self.session.refresh(report)
        if report.maintenance is not None:
            # Recarga los repuestos utilizados, agregados después de cargar el mantenimiento.
            self.session.refresh(report.maintenance)
        return report
