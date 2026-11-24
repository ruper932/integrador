"""Reubicación de atrapanieblas.

Flujo: un docente solicita mover un atrapanieblas (p. ej. porque el espacio ya no es adecuado) y la
solicitud queda `pendiente` → el personal de mantenimiento recibe un aviso y la acepta (`aceptado`)
→ inicia el traslado (`en_progreso`) → lo finaliza indicando la nueva ubicación (`finalizado`): el
atrapanieblas y sus estaciones IoT pasan a esa ubicación, con historial. Mientras no se haya
iniciado, el personal puede rechazarla explicando el motivo (`rechazado`).
Quien solicita recibe un aviso en cada etapa; el administrador y el director ven todo el proceso.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session

from app.business.services.audit_service import AuditService
from app.business.services.context import RequestContext
from app.business.services.device_service import DeviceService
from app.business.services.integrity import integrity_guard
from app.business.services.notification_service import NotificationService
from app.core.clock import utcnow
from app.core.errors import BusinessRuleError, ConflictError, ForbiddenError, NotFoundError
from app.core.permissions import Permission
from app.data.models.infrastructure import FogCollector, Location
from app.data.models.relocations import FogCollectorRelocation
from app.data.models.security import User
from app.data.repositories.iot import FogCollectorRepository, LocationRepository
from app.data.repositories.relocations import RelocationRepository
from app.data.repositories.security import UserRepository

Scope = Literal["mine", "open", "assigned", "all"]
SCOPE_PERMISSION: dict[Scope, Permission] = {
    "mine": Permission.RELOCATIONS_REQUEST,
    "open": Permission.RELOCATIONS_ATTEND,
    "assigned": Permission.RELOCATIONS_ATTEND,
    "all": Permission.RELOCATIONS_SUPERVISE,
}
REASON_LABELS = {
    "espacio_insuficiente": "espacio insuficiente",
    "interferencia_con_actividades": "interfiere con otras actividades",
    "obstruccion_de_la_niebla": "obstrucción de la niebla o el viento",
    "otro": "otro motivo",
}


@dataclass(frozen=True)
class RelocationFilters:
    fog_collector_id: int | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


@dataclass(frozen=True)
class RelocationSummary:
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


class RelocationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.relocations = RelocationRepository(session)
        self.fog_collectors = FogCollectorRepository(session)
        self.locations = LocationRepository(session)
        self.users = UserRepository(session)
        self.devices = DeviceService(session)
        self.notifications = NotificationService(session)
        self.audit = AuditService(session)

    # --- Consulta -------------------------------------------------------------

    def search(
        self,
        ctx: RequestContext,
        *,
        scope: Scope,
        status: str | None,
        offset: int,
        limit: int,
        filters: RelocationFilters | None = None,
    ) -> tuple[Sequence[FogCollectorRelocation], int]:
        user = _require_user(ctx)
        if not _has(user, SCOPE_PERMISSION[scope]):
            raise ForbiddenError("No tiene permiso para consultar estas solicitudes.")
        f = filters or RelocationFilters()
        common = {
            "offset": offset,
            "limit": limit,
            "fog_collector_id": f.fog_collector_id,
            "date_from": f.date_from,
            "date_to": f.date_to,
        }
        if scope == "mine":
            return self.relocations.search(**common, requested_by_id=user.id, status=status)
        if scope == "open":
            return self.relocations.search(**common, status="pendiente", oldest_first=True)
        if scope == "assigned":
            return self.relocations.search(**common, assigned_to_id=user.id, status=status)
        return self.relocations.search(**common, status=status)

    def get(self, ctx: RequestContext, relocation_id: int) -> FogCollectorRelocation:
        user = _require_user(ctx)
        relocation = self.relocations.get(relocation_id)
        visible = relocation is not None and (
            relocation.requested_by_id == user.id
            or _has(user, Permission.RELOCATIONS_ATTEND)
            or _has(user, Permission.RELOCATIONS_SUPERVISE)
        )
        # Una solicitud ajena se informa como inexistente para no revelar su existencia.
        if relocation is None or not visible:
            raise NotFoundError("Solicitud de reubicación no encontrada.")
        return relocation

    def summary(self, ctx: RequestContext) -> RelocationSummary:
        user = _require_user(ctx)
        attend = _has(user, Permission.RELOCATIONS_ATTEND)
        assigned = self.relocations.count_by_status(assigned_to_id=user.id) if attend else {}
        return RelocationSummary(
            mine=self.relocations.count_by_status(requested_by_id=user.id)
            if _has(user, Permission.RELOCATIONS_REQUEST)
            else None,
            open=self.relocations.count_by_status().get("pendiente", 0) if attend else None,
            assigned_active=assigned.get("aceptado", 0) + assigned.get("en_progreso", 0) if attend else None,
            all=self.relocations.count_by_status() if _has(user, Permission.RELOCATIONS_SUPERVISE) else None,
        )

    # --- Solicitud ------------------------------------------------------------

    def request(
        self,
        ctx: RequestContext,
        *,
        fog_collector_id: int,
        reason: str,
        description: str,
        proposed_location_id: int | None,
        proposed_place: str | None,
    ) -> FogCollectorRelocation:
        user = _require_user(ctx)
        fog_collector = self._active_fog_collector(fog_collector_id)
        current = self.relocations.active_for(fog_collector.id)
        if current is not None:
            raise ConflictError(
                f"El atrapanieblas ya tiene una solicitud de reubicación en curso (#{current.id}).",
                code="reubicacion_en_curso",
            )
        if proposed_location_id is not None:
            self._destination(fog_collector, proposed_location_id, label="propuesta")
        with integrity_guard(
            self.session, duplicate_message="El atrapanieblas ya tiene una solicitud de reubicación en curso."
        ):
            relocation = self.relocations.add(
                FogCollectorRelocation(
                    fog_collector_id=fog_collector.id,
                    requested_by_id=user.id,
                    reason=reason,
                    description=description,
                    origin_location_id=fog_collector.location_id,
                    proposed_location_id=proposed_location_id,
                    proposed_place=proposed_place,
                    status="pendiente",
                )
            )
        attenders = [u.id for u in self.users.active_with_permission(Permission.RELOCATIONS_ATTEND) if u.id != user.id]
        self.notifications.notify(
            attenders,
            "Nueva solicitud de reubicación",
            f"{user.full_name} solicitó reubicar «{fog_collector.name}» ({REASON_LABELS[reason]}).",
            relocation_id=relocation.id,
        )
        self.audit.record(
            ctx,
            "reubicacion.solicitar",
            entity_type="fog_collector_relocation",
            entity_id=relocation.id,
            details={
                "fog_collector_id": fog_collector.id,
                "motivo": reason,
                "origen": fog_collector.location_id,
                "propuesta": proposed_location_id,
            },
        )
        return self._commit(relocation)

    # --- Atención -------------------------------------------------------------

    def accept(self, ctx: RequestContext, relocation_id: int) -> FogCollectorRelocation:
        user = _require_user(ctx)
        # El bloqueo evita que dos personas acepten la misma solicitud a la vez.
        relocation = self._locked(relocation_id)
        if relocation.status != "pendiente":
            if relocation.assignee is not None and relocation.status in ("aceptado", "en_progreso"):
                raise ConflictError(
                    f"La solicitud ya fue aceptada por {relocation.assignee.full_name}.", code="reubicacion_ya_aceptada"
                )
            raise BusinessRuleError("Solo se puede aceptar una solicitud pendiente.", code="transicion_invalida")
        self._active_fog_collector(relocation.fog_collector_id)
        relocation.status = "aceptado"
        relocation.assigned_to_id = user.id
        relocation.accepted_at = utcnow()
        self._notify_requester(
            relocation,
            "Su solicitud de reubicación fue aceptada",
            f"{user.full_name} aceptó reubicar «{relocation.fog_collector.name}».",
        )
        self._audit(ctx, "reubicacion.aceptar", relocation)
        return self._commit(relocation)

    def start(self, ctx: RequestContext, relocation_id: int) -> FogCollectorRelocation:
        user = _require_user(ctx)
        relocation = self._assigned(user, relocation_id)
        if relocation.status != "aceptado":
            raise BusinessRuleError("Solo se puede iniciar una reubicación aceptada.", code="transicion_invalida")
        relocation.status = "en_progreso"
        relocation.started_at = utcnow()
        self._notify_requester(
            relocation,
            "Reubicación en progreso",
            f"{user.full_name} inició el traslado de «{relocation.fog_collector.name}».",
        )
        self._audit(ctx, "reubicacion.iniciar", relocation)
        return self._commit(relocation)

    def finish(
        self,
        ctx: RequestContext,
        relocation_id: int,
        *,
        destination_location_id: int,
        new_orientation: str | None,
        work_notes: str,
    ) -> FogCollectorRelocation:
        user = _require_user(ctx)
        relocation = self._assigned(user, relocation_id)
        if relocation.status != "en_progreso":
            raise BusinessRuleError("Solo se puede finalizar una reubicación en progreso.", code="transicion_invalida")
        fog_collector = self._active_fog_collector(relocation.fog_collector_id, lock=True)
        destination = self._destination(fog_collector, destination_location_id, label="de destino")

        now = utcnow()
        relocation.destination_location_id = destination.id
        relocation.previous_orientation = fog_collector.orientation
        relocation.new_orientation = new_orientation
        relocation.work_notes = work_notes
        relocation.finished_at = now
        relocation.status = "finalizado"
        fog_collector.location_id = destination.id
        if new_orientation is not None:
            fog_collector.orientation = new_orientation
        # Las estaciones IoT montadas en el atrapanieblas se trasladan con él (con historial).
        moved = self.devices.follow_fog_collector(fog_collector.id, destination.id)
        self._notify_requester(
            relocation,
            "Reubicación finalizada",
            f"{user.full_name} trasladó «{fog_collector.name}» a «{destination.name}».",
        )
        self._audit(
            ctx,
            "reubicacion.finalizar",
            relocation,
            details={
                "origen": relocation.origin_location_id,
                "destino": destination.id,
                "orientacion": new_orientation,
                "estaciones_trasladadas": moved,
            },
        )
        return self._commit(relocation)

    def reject(self, ctx: RequestContext, relocation_id: int, *, reason: str) -> FogCollectorRelocation:
        user = _require_user(ctx)
        relocation = self._locked(relocation_id)
        if relocation.status == "pendiente":
            relocation.assigned_to_id = user.id  # queda registrado quién la rechazó
        elif relocation.status == "aceptado":
            if relocation.assigned_to_id != user.id:
                raise ForbiddenError("Solo el personal asignado puede rechazar esta solicitud.")
        else:
            raise BusinessRuleError(
                "Solo se puede rechazar una solicitud pendiente o aceptada que aún no se inició.",
                code="transicion_invalida",
            )
        relocation.status = "rechazado"
        relocation.rejection_reason = reason
        relocation.finished_at = utcnow()
        self._notify_requester(
            relocation,
            "Su solicitud de reubicación fue rechazada",
            f"{user.full_name} rechazó reubicar «{relocation.fog_collector.name}»: {reason}"[:500],
        )
        self._audit(ctx, "reubicacion.rechazar", relocation)
        return self._commit(relocation)

    # --- Auxiliares -------------------------------------------------------------

    def _active_fog_collector(self, fog_collector_id: int, *, lock: bool = False) -> FogCollector:
        fog_collector = (
            self.fog_collectors.get_for_update(fog_collector_id) if lock else self.fog_collectors.get(fog_collector_id)
        )
        if fog_collector is None:
            raise BusinessRuleError("El atrapanieblas indicado no existe.", code="referencia_inexistente")
        if not fog_collector.is_active:
            raise BusinessRuleError("El atrapanieblas está desactivado.", code="atrapanieblas_inactivo")
        return fog_collector

    def _destination(self, fog_collector: FogCollector, location_id: int, *, label: str) -> Location:
        location = self.locations.get(location_id)
        if location is None or not location.is_active:
            raise BusinessRuleError(f"La ubicación {label} no existe o está desactivada.", code="ubicacion_invalida")
        if location.id == fog_collector.location_id:
            raise BusinessRuleError(
                f"La ubicación {label} debe ser distinta de la ubicación actual del atrapanieblas.",
                code="misma_ubicacion",
            )
        return location

    def _locked(self, relocation_id: int) -> FogCollectorRelocation:
        relocation = self.relocations.get_for_update(relocation_id)
        if relocation is None:
            raise NotFoundError("Solicitud de reubicación no encontrada.")
        return relocation

    def _assigned(self, user: User, relocation_id: int) -> FogCollectorRelocation:
        relocation = self._locked(relocation_id)
        if relocation.status == "pendiente":
            raise BusinessRuleError("La solicitud todavía no fue aceptada.", code="transicion_invalida")
        if relocation.assigned_to_id != user.id:
            raise ForbiddenError("Solo el personal asignado puede actualizar esta reubicación.")
        return relocation

    def _notify_requester(self, relocation: FogCollectorRelocation, title: str, message: str) -> None:
        # Quien actúa es siempre el asignado: no se avisa a sí mismo si también hizo la solicitud.
        if relocation.requested_by_id != (relocation.assigned_to_id or 0):
            self.notifications.notify([relocation.requested_by_id], title, message, relocation_id=relocation.id)

    def _audit(
        self, ctx: RequestContext, action: str, relocation: FogCollectorRelocation, details: dict | None = None
    ) -> None:
        self.audit.record(
            ctx,
            action,
            entity_type="fog_collector_relocation",
            entity_id=relocation.id,
            details={"fog_collector_id": relocation.fog_collector_id, **(details or {})},
        )

    def _commit(self, relocation: FogCollectorRelocation) -> FogCollectorRelocation:
        self.session.commit()
        self.session.refresh(relocation)
        return relocation
