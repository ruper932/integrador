"""Registro y consulta de auditoría."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.business.services.context import RequestContext
from app.data.models.security import AuditLog
from app.data.repositories.security import AuditLogRepository

# Claves que nunca deben quedar en el detalle de auditoría.
_SENSITIVE_KEYS = {"password", "new_password", "current_password", "temporary_password", "token", "api_key", "key"}


def _scrub(details: dict[str, Any] | None) -> dict[str, Any] | None:
    if details is None:
        return None
    return {k: ("***" if k in _SENSITIVE_KEYS else v) for k, v in details.items()}


class AuditService:
    def __init__(self, session: Session) -> None:
        self.repo = AuditLogRepository(session)

    def record(
        self,
        ctx: RequestContext,
        action: str,
        *,
        entity_type: str | None = None,
        entity_id: int | str | None = None,
        details: dict[str, Any] | None = None,
        user_id: int | None = None,
    ) -> AuditLog:
        """Agrega un registro a la transacción actual (el llamador hace commit)."""
        return self.repo.add(
            AuditLog(
                user_id=user_id if user_id is not None else ctx.user_id,
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id is not None else None,
                details=_scrub(details),
                ip_address=ctx.ip,
            )
        )

    def search(
        self,
        *,
        offset: int,
        limit: int,
        user_id: int | None,
        action: str | None,
        entity_type: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> tuple[Sequence[AuditLog], int]:
        return self.repo.search(
            offset=offset,
            limit=limit,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            date_from=date_from,
            date_to=date_to,
        )
