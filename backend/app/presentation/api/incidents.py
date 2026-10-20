"""Endpoints de reportes de incidencia (atención mediante mantenimientos) y notificaciones."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.business.services.incident_service import IncidentService
from app.business.services.maintenance_service import UsedPart
from app.business.services.notification_service import NotificationService
from app.core.permissions import Permission
from app.data.models.incidents import IncidentReport
from app.data.models.security import User
from app.presentation.api.deps import AuthContext, CurrentAuth, DbSession, require, require_any
from app.presentation.api.inventory import to_maintenance_out
from app.presentation.schemas.common import Message, Page
from app.presentation.schemas.incidents import (
    IncidentFinishIn,
    IncidentIn,
    IncidentOut,
    IncidentScope,
    IncidentStatus,
    IncidentSummaryOut,
    NotificationOut,
    NotificationsOut,
    PersonOut,
)

router = APIRouter(tags=["Reportes de incidencia"])

Reporter = Annotated[AuthContext, Depends(require(Permission.INCIDENTS_REPORT))]
Attender = Annotated[AuthContext, Depends(require(Permission.INCIDENTS_ATTEND))]
IncidentReader = Annotated[
    AuthContext,
    Depends(require_any(Permission.INCIDENTS_REPORT, Permission.INCIDENTS_ATTEND, Permission.INCIDENTS_SUPERVISE)),
]


def _person(user: User) -> PersonOut:
    return PersonOut(id=user.id, username=user.username, full_name=user.full_name)


def to_incident_out(report: IncidentReport) -> IncidentOut:
    record = report.maintenance
    return IncidentOut(
        id=report.id,
        title=report.title,
        description=report.description,
        priority=report.priority,  # type: ignore[arg-type]
        location_reference=report.location_reference,
        status=report.status,  # type: ignore[arg-type]
        device_id=report.device_id,
        device_code=report.device.code if report.device else None,
        device_name=report.device.name if report.device else None,
        sensor_id=report.sensor_id,
        sensor_code=report.sensor.code if report.sensor else None,
        source=report.source,  # type: ignore[arg-type]
        auto_cause=report.auto_cause,  # type: ignore[arg-type]
        reporter=_person(report.reporter) if report.reporter else None,
        assignee=_person(record.user) if record else None,
        created_at=report.created_at,
        maintenance=to_maintenance_out(record) if record else None,
    )


@router.post(
    "/incidents",
    response_model=IncidentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Reportar una incidencia (avisa al personal de mantenimiento)",
)
def create_incident(payload: IncidentIn, db: DbSession, auth: Reporter) -> IncidentOut:
    report = IncidentService(db).report(
        auth.ctx,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        location_reference=payload.location_reference,
        device_id=payload.device_id,
        sensor_id=payload.sensor_id,
    )
    return to_incident_out(report)


@router.get(
    "/incidents",
    response_model=Page[IncidentOut],
    summary="Listar reportes: propios (mine), por atender (open), asignados (assigned) o todos (all)",
)
def list_incidents(
    db: DbSession,
    auth: IncidentReader,
    scope: IncidentScope = "mine",
    status_filter: Annotated[IncidentStatus | None, Query(alias="status")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Page[IncidentOut]:
    reports, total = IncidentService(db).search(auth.ctx, scope=scope, status=status_filter, offset=offset, limit=limit)
    return Page(items=[to_incident_out(r) for r in reports], total=total, offset=offset, limit=limit)


@router.get("/incidents/summary", response_model=IncidentSummaryOut, summary="Conteo de reportes por estado")
def incidents_summary(db: DbSession, auth: IncidentReader) -> IncidentSummaryOut:
    summary = IncidentService(db).summary(auth.ctx)
    return IncidentSummaryOut(
        mine=summary.mine, open=summary.open, assigned_active=summary.assigned_active, all=summary.all
    )


@router.get("/incidents/{report_id}", response_model=IncidentOut)
def get_incident(report_id: int, db: DbSession, auth: IncidentReader) -> IncidentOut:
    return to_incident_out(IncidentService(db).get(auth.ctx, report_id))


@router.post("/incidents/{report_id}/accept", response_model=IncidentOut, summary="Aceptar el reporte")
def accept_incident(report_id: int, db: DbSession, auth: Attender) -> IncidentOut:
    return to_incident_out(IncidentService(db).accept(auth.ctx, report_id))


@router.post("/incidents/{report_id}/start", response_model=IncidentOut, summary="Iniciar el mantenimiento")
def start_incident(report_id: int, db: DbSession, auth: Attender) -> IncidentOut:
    return to_incident_out(IncidentService(db).start(auth.ctx, report_id))


@router.post(
    "/incidents/{report_id}/finish",
    response_model=IncidentOut,
    summary="Finalizar el mantenimiento (descuenta los repuestos del inventario)",
)
def finish_incident(report_id: int, payload: IncidentFinishIn, db: DbSession, auth: Attender) -> IncidentOut:
    report = IncidentService(db).finish(
        auth.ctx,
        report_id,
        device_id=payload.device_id,
        sensor_id=payload.sensor_id,
        maintenance_type=payload.maintenance_type,
        description=payload.description,
        final_status=payload.final_status,
        parts=[UsedPart(item_id=p.item_id, quantity=p.quantity) for p in payload.parts],
    )
    return to_incident_out(report)


# --- Notificaciones (cada usuario solo ve las suyas) ------------------------------


@router.get("/notifications", response_model=NotificationsOut, tags=["Notificaciones"])
def list_notifications(
    db: DbSession,
    auth: CurrentAuth,
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> NotificationsOut:
    items, unread = NotificationService(db).list(auth.user.id, limit=limit, unread_only=unread_only)
    return NotificationsOut(items=[NotificationOut.model_validate(n) for n in items], unread=unread)


@router.post("/notifications/{notification_id}/read", response_model=Message, tags=["Notificaciones"])
def read_notification(notification_id: int, db: DbSession, auth: CurrentAuth) -> Message:
    NotificationService(db).mark_read(auth.user.id, notification_id)
    return Message(message="Notificación marcada como leída.")


@router.post("/notifications/read-all", response_model=Message, tags=["Notificaciones"])
def read_all_notifications(db: DbSession, auth: CurrentAuth) -> Message:
    count = NotificationService(db).mark_all_read(auth.user.id)
    return Message(message=f"{count} notificaciones marcadas como leídas.")
