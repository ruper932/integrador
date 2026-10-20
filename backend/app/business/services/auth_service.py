"""Autenticación: inicio y cierre de sesión, sesiones y cambio de contraseña."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import NoReturn

from sqlalchemy.orm import Session

from app.business.rules.passwords import validate_password_policy
from app.business.services.audit_service import AuditService
from app.business.services.context import RequestContext
from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.errors import BusinessRuleError, UnauthorizedError
from app.core.security import generate_token, hash_password, keyed_hash, verify_dummy_password, verify_password
from app.data.models.security import User, UserSession
from app.data.repositories.security import UserRepository, UserSessionRepository

INVALID_CREDENTIALS = "Usuario o contraseña incorrectos, o la cuenta no está disponible."


@dataclass(frozen=True)
class LoginResult:
    token: str
    user: User
    expires_at: datetime


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.sessions = UserSessionRepository(session)
        self.audit = AuditService(session)
        self.settings = get_settings()

    def login(self, ctx: RequestContext, username: str, password: str) -> LoginResult:
        now = utcnow()
        user = self.users.get_by_username(username)
        if user is None:
            verify_dummy_password(password)
            self._fail(ctx, username, None, "usuario_inexistente")

        if user.locked_until and user.locked_until > now:
            self._fail(ctx, username, user, "cuenta_bloqueada")

        if not verify_password(password, user.password_hash):
            user.failed_login_attempts += 1
            reason = "contrasena_incorrecta"
            if user.failed_login_attempts >= self.settings.login_max_failed_attempts:
                user.locked_until = now + timedelta(minutes=self.settings.login_lockout_minutes)
                user.failed_login_attempts = 0
                reason = "cuenta_bloqueada_por_intentos"
            self._fail(ctx, username, user, reason)

        if not user.is_active:
            self._fail(ctx, username, user, "usuario_inactivo")

        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = now
        token = generate_token()
        expires_at = now + timedelta(minutes=self.settings.session_ttl_minutes)
        self.sessions.add(
            UserSession(
                user_id=user.id,
                token_hash=keyed_hash(token),
                expires_at=expires_at,
                ip_address=ctx.ip,
                user_agent=(ctx.user_agent or "")[:255] or None,
            )
        )
        self.audit.record(ctx, "auth.login", entity_type="user", entity_id=user.id, user_id=user.id)
        self.session.commit()
        return LoginResult(token=token, user=user, expires_at=expires_at)

    def _fail(self, ctx: RequestContext, username: str, user: User | None, reason: str) -> NoReturn:
        self.audit.record(
            ctx,
            "auth.login_fallido",
            entity_type="user",
            entity_id=user.id if user else None,
            details={"username": username[:64], "motivo": reason},
        )
        self.session.commit()
        raise UnauthorizedError(INVALID_CREDENTIALS, code="credenciales_invalidas")

    def authenticate(self, token: str) -> tuple[UserSession, User]:
        user_session = self.sessions.get_active_by_token_hash(keyed_hash(token), utcnow())
        if user_session is None or not user_session.user.is_active:
            raise UnauthorizedError("La sesión no es válida o ha expirado.", code="sesion_invalida")
        return user_session, user_session.user

    def logout(self, ctx: RequestContext, user_session: UserSession) -> None:
        user_session.revoked_at = utcnow()
        self.audit.record(ctx, "auth.logout", entity_type="user", entity_id=user_session.user_id)
        self.session.commit()

    def change_password(
        self, ctx: RequestContext, user: User, current_session: UserSession, current_password: str, new_password: str
    ) -> None:
        if not verify_password(current_password, user.password_hash):
            raise BusinessRuleError("La contraseña actual no es correcta.", code="contrasena_actual_incorrecta")
        if current_password == new_password:
            raise BusinessRuleError("La nueva contraseña debe ser distinta de la actual.", code="contrasena_repetida")
        validate_password_policy(new_password, username=user.username)
        now = utcnow()
        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        user.password_changed_at = now
        self.sessions.revoke_all_for_user(user.id, now, except_id=current_session.id)
        self.audit.record(ctx, "auth.cambio_contrasena", entity_type="user", entity_id=user.id)
        self.session.commit()
