"""Endpoints administrativos: recuperación de cuenta y auditoría."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.business.services.audit_service import AuditService
from app.business.services.recovery_service import RecoveryService
from app.core.permissions import Permission
from app.data.models.security import AccountRecoveryRequest
from app.presentation.api.deps import AuthContext, DbSession, require
from app.presentation.schemas.common import Page
from app.presentation.schemas.security import (
    AuditLogOut,
    RecoveryApprovalOut,
    RecoveryApprove,
    RecoveryReject,
    RecoveryRequestOut,
)

router = APIRouter(prefix="/admin", tags=["Administración"])

RecoveryAdmin = Annotated[AuthContext, Depends(require(Permission.RECOVERY_MANAGE))]
AuditReader = Annotated[AuthContext, Depends(require(Permission.AUDIT_READ))]


def to_recovery_out(request: AccountRecoveryRequest) -> RecoveryRequestOut:
    out = RecoveryRequestOut.model_validate(request)
    return out.model_copy(update={"user_full_name": request.user.full_name if request.user else None})


@router.get("/recovery-requests", response_model=Page[RecoveryRequestOut])
def list_recovery_requests(
    db: DbSession,
    _: RecoveryAdmin,
    status: Literal["pendiente", "aprobada", "rechazada"] | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Page[RecoveryRequestOut]:
    items, total = RecoveryService(db).list(offset=offset, limit=limit, status=status)
    return Page(items=[to_recovery_out(r) for r in items], total=total, offset=offset, limit=limit)


@router.post("/recovery-requests/{request_id}/approve", response_model=RecoveryApprovalOut)
def approve_recovery_request(
    request_id: int, payload: RecoveryApprove, db: DbSession, auth: RecoveryAdmin
) -> RecoveryApprovalOut:
    result = RecoveryService(db).approve(
        auth.ctx,
        request_id,
        identity_verified=payload.identity_verified,
        verification_note=payload.verification_note,
        new_password=payload.new_password,
    )
    return RecoveryApprovalOut(request=to_recovery_out(result.request), temporary_password=result.temporary_password)


@router.post("/recovery-requests/{request_id}/reject", response_model=RecoveryRequestOut)
def reject_recovery_request(
    request_id: int, payload: RecoveryReject, db: DbSession, auth: RecoveryAdmin
) -> RecoveryRequestOut:
    return to_recovery_out(RecoveryService(db).reject(auth.ctx, request_id, reason=payload.reason))


@router.get("/audit-logs", response_model=Page[AuditLogOut])
def list_audit_logs(
    db: DbSession,
    _: AuditReader,
    user_id: int | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> Page[AuditLogOut]:
    items, total = AuditService(db).search(
        offset=offset,
        limit=limit,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        date_from=date_from,
        date_to=date_to,
    )
    return Page(
        items=[
            AuditLogOut.model_validate(log).model_copy(update={"username": log.user.username if log.user else None})
            for log in items
        ],
        total=total,
        offset=offset,
        limit=limit,
    )
