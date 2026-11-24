"""Endpoints de solicitudes de reubicación de atrapanieblas."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import AwareDatetime

from app.business.services.relocation_service import RelocationFilters, RelocationService
from app.core.permissions import Permission
from app.data.models.infrastructure import Location
from app.data.models.relocations import FogCollectorRelocation
from app.data.models.security import User
from app.presentation.api.deps import AuthContext, DbSession, require, require_any
from app.presentation.schemas.common import Page
from app.presentation.schemas.incidents import PersonOut
from app.presentation.schemas.relocations import (
    FogCollectorRefOut,
    PlaceOut,
    RelocationFinishIn,
    RelocationIn,
    RelocationOut,
    RelocationRejectIn,
    RelocationScope,
    RelocationStatus,
    RelocationSummaryOut,
)

router = APIRouter(tags=["Reubicación de atrapanieblas"])

Requester = Annotated[AuthContext, Depends(require(Permission.RELOCATIONS_REQUEST))]
Attender = Annotated[AuthContext, Depends(require(Permission.RELOCATIONS_ATTEND))]
Reader = Annotated[
    AuthContext,
    Depends(
        require_any(Permission.RELOCATIONS_REQUEST, Permission.RELOCATIONS_ATTEND, Permission.RELOCATIONS_SUPERVISE)
    ),
]


def _person(user: User) -> PersonOut:
    return PersonOut(id=user.id, username=user.username, full_name=user.full_name)


def _place(location: Location | None) -> PlaceOut | None:
    return PlaceOut(id=location.id, name=location.name) if location else None


def to_relocation_out(r: FogCollectorRelocation) -> RelocationOut:
    return RelocationOut(
        id=r.id,
        status=r.status,  # type: ignore[arg-type]
        reason=r.reason,  # type: ignore[arg-type]
        description=r.description,
        fog_collector=FogCollectorRefOut(id=r.fog_collector.id, code=r.fog_collector.code, name=r.fog_collector.name),
        origin_location=_place(r.origin_location),
        proposed_location=_place(r.proposed_location),
        proposed_place=r.proposed_place,
        destination_location=_place(r.destination_location),
        previous_orientation=r.previous_orientation,
        new_orientation=r.new_orientation,
        work_notes=r.work_notes,
        rejection_reason=r.rejection_reason,
        requester=_person(r.requester),
        assignee=_person(r.assignee) if r.assignee else None,
        created_at=r.created_at,
        accepted_at=r.accepted_at,
        started_at=r.started_at,
        finished_at=r.finished_at,
    )


@router.post(
    "/relocations",
    response_model=RelocationOut,
    status_code=status.HTTP_201_CREATED,
    summary="Solicitar la reubicación de un atrapanieblas (avisa al personal de mantenimiento)",
)
def create_relocation(payload: RelocationIn, db: DbSession, auth: Requester) -> RelocationOut:
    relocation = RelocationService(db).request(
        auth.ctx,
        fog_collector_id=payload.fog_collector_id,
        reason=payload.reason,
        description=payload.description,
        proposed_location_id=payload.proposed_location_id,
        proposed_place=payload.proposed_place,
    )
    return to_relocation_out(relocation)


@router.get(
    "/relocations",
    response_model=Page[RelocationOut],
    summary="Listar solicitudes: propias (mine), por atender (open), asignadas (assigned) o todas (all)",
)
def list_relocations(
    db: DbSession,
    auth: Reader,
    scope: RelocationScope = "mine",
    status_filter: Annotated[RelocationStatus | None, Query(alias="status")] = None,
    fog_collector_id: int | None = None,
    date_from: AwareDatetime | None = None,
    date_to: AwareDatetime | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Page[RelocationOut]:
    items, total = RelocationService(db).search(
        auth.ctx,
        scope=scope,
        status=status_filter,
        offset=offset,
        limit=limit,
        filters=RelocationFilters(fog_collector_id=fog_collector_id, date_from=date_from, date_to=date_to),
    )
    return Page(items=[to_relocation_out(r) for r in items], total=total, offset=offset, limit=limit)


@router.get("/relocations/summary", response_model=RelocationSummaryOut, summary="Conteo de solicitudes por estado")
def relocations_summary(db: DbSession, auth: Reader) -> RelocationSummaryOut:
    s = RelocationService(db).summary(auth.ctx)
    return RelocationSummaryOut(mine=s.mine, open=s.open, assigned_active=s.assigned_active, all=s.all)


@router.get("/relocations/{relocation_id}", response_model=RelocationOut)
def get_relocation(relocation_id: int, db: DbSession, auth: Reader) -> RelocationOut:
    return to_relocation_out(RelocationService(db).get(auth.ctx, relocation_id))


@router.post("/relocations/{relocation_id}/accept", response_model=RelocationOut, summary="Aceptar la solicitud")
def accept_relocation(relocation_id: int, db: DbSession, auth: Attender) -> RelocationOut:
    return to_relocation_out(RelocationService(db).accept(auth.ctx, relocation_id))


@router.post("/relocations/{relocation_id}/start", response_model=RelocationOut, summary="Iniciar el traslado")
def start_relocation(relocation_id: int, db: DbSession, auth: Attender) -> RelocationOut:
    return to_relocation_out(RelocationService(db).start(auth.ctx, relocation_id))


@router.post(
    "/relocations/{relocation_id}/finish",
    response_model=RelocationOut,
    summary="Finalizar el traslado (actualiza la ubicación del atrapanieblas y de sus estaciones)",
)
def finish_relocation(relocation_id: int, payload: RelocationFinishIn, db: DbSession, auth: Attender) -> RelocationOut:
    relocation = RelocationService(db).finish(
        auth.ctx,
        relocation_id,
        destination_location_id=payload.destination_location_id,
        new_orientation=payload.new_orientation,
        work_notes=payload.work_notes,
    )
    return to_relocation_out(relocation)


@router.post(
    "/relocations/{relocation_id}/reject",
    response_model=RelocationOut,
    summary="Rechazar la solicitud indicando el motivo (antes de iniciar el traslado)",
)
def reject_relocation(relocation_id: int, payload: RelocationRejectIn, db: DbSession, auth: Attender) -> RelocationOut:
    return to_relocation_out(RelocationService(db).reject(auth.ctx, relocation_id, reason=payload.reason))
