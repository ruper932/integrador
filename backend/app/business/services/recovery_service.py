"""Recuperación de cuenta mediante solicitud presencial al administrador.

No se envían enlaces ni códigos por canales externos. El flujo es:
solicitud (pendiente) -> verificación presencial -> aprobación/rechazo por un
administrador -> contraseña temporal con cambio obligatorio.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from app.business.services.audit_service import AuditService
from app.business.services.context import RequestContext
from app.business.services.user_service import UserService
from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.errors import BusinessRuleError, NotFoundError, TooManyRequestsError
from app.data.models.security import AccountRecoveryRequest
from app.data.repositories.security import RecoveryRequestRepository, UserRepository

STATUS_PENDING = "pendiente"
STATUS_APPROVED = "aprobada"
STATUS_REJECTED = "rechazada"

PUBLIC_ACK = (
    "Si la cuenta existe, la solicitud quedó registrada. Acérquese al administrador del sistema "
    "para verificar su identidad."
)


@dataclass(frozen=True)
class ApprovalResult:
    request: AccountRecoveryRequest
    temporary_password: str | None


class RecoveryService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.requests = RecoveryRequestRepository(session)
        self.users = UserRepository(session)
        self.audit = AuditService(session)
        self.settings = get_settings()

    def submit(self, ctx: RequestContext, username: str, message: str | None) -> None:
        """Registra una solicitud. La respuesta pública no revela si el usuario existe."""
        now = utcnow()
        if ctx.ip and self.requests.count_by_ip_since(ctx.ip, now - timedelta(hours=1)) >= (
            self.settings.recovery_max_per_ip_per_hour
        ):
            raise TooManyRequestsError("Se superó el límite de solicitudes. Intente más tarde.")

        if self.requests.count_by_username_since(username, now - timedelta(days=1)) >= (
            self.settings.recovery_max_per_username_per_day
        ):
            # Se responde igual que en el caso exitoso para no revelar información.
            self.audit.record(ctx, "recuperacion.limite_usuario", details={"username": username[:64]})
            self.session.commit()
            return

        user = self.users.get_by_username(username)
        request = self.requests.add(
            AccountRecoveryRequest(
                username_requested=username[:64],
                user_id=user.id if user else None,
                status=STATUS_PENDING,
                message=message,
                requester_ip=ctx.ip,
            )
        )
        self.audit.record(ctx, "recuperacion.solicitar", entity_type="recovery_request", entity_id=request.id)
        self.session.commit()

    def list(self, *, offset: int, limit: int, status: str | None) -> tuple[Sequence[AccountRecoveryRequest], int]:
        return self.requests.search(offset=offset, limit=limit, status=status)

    def _get_pending(self, request_id: int) -> AccountRecoveryRequest:
        request = self.requests.get_for_update(request_id)
        if request is None:
            raise NotFoundError("Solicitud de recuperación no encontrada.")
        if request.status != STATUS_PENDING:
            raise BusinessRuleError("La solicitud ya fue resuelta.", code="solicitud_resuelta")
        return request

    def approve(
        self,
        ctx: RequestContext,
        request_id: int,
        *,
        identity_verified: bool,
        verification_note: str,
        new_password: str | None,
    ) -> ApprovalResult:
        if not identity_verified:
            raise BusinessRuleError(
                "Debe confirmar que verificó presencialmente la identidad del solicitante.",
                code="identidad_no_verificada",
            )
        request = self._get_pending(request_id)
        if request.user is None:
            raise BusinessRuleError(
                "La solicitud no corresponde a un usuario registrado; debe rechazarse.", code="usuario_inexistente"
            )
        if not request.user.is_active:
            raise BusinessRuleError(
                "El usuario está desactivado. Reactívelo antes de aprobar la solicitud.", code="usuario_inactivo"
            )
        temporary = UserService(self.session).apply_password_reset(request.user, new_password)
        request.status = STATUS_APPROVED
        request.resolved_at = utcnow()
        request.resolved_by_id = ctx.user_id
        request.resolution_note = verification_note
        self.audit.record(
            ctx,
            "recuperacion.aprobar",
            entity_type="recovery_request",
            entity_id=request.id,
            details={"user_id": request.user_id, "modo": "temporal" if temporary else "definida"},
        )
        self.session.commit()
        return ApprovalResult(request=request, temporary_password=temporary)

    def reject(self, ctx: RequestContext, request_id: int, *, reason: str) -> AccountRecoveryRequest:
        request = self._get_pending(request_id)
        request.status = STATUS_REJECTED
        request.resolved_at = utcnow()
        request.resolved_by_id = ctx.user_id
        request.resolution_note = reason
        self.audit.record(ctx, "recuperacion.rechazar", entity_type="recovery_request", entity_id=request.id)
        self.session.commit()
        return request
