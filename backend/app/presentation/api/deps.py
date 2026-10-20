"""Dependencias de FastAPI: sesión de base de datos, autenticación y autorización."""

import ipaddress
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import APIKeyCookie
from sqlalchemy.orm import Session

from app.business.services.auth_service import AuthService
from app.business.services.context import RequestContext
from app.business.services.device_service import DeviceAuthService
from app.core.config import get_settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.permissions import Permission
from app.data.database import get_session
from app.data.models.iot import Device
from app.data.models.security import User, UserSession

DbSession = Annotated[Session, Depends(get_session)]

# La sesión viaja en una cookie HttpOnly + SameSite=Strict (no se expone a JavaScript).
_session_cookie = APIKeyCookie(name=get_settings().session_cookie_name, auto_error=False)

# Rutas que un usuario con contraseña temporal puede usar antes de cambiarla.
PASSWORD_CHANGE_ALLOWED_PATHS = {"/api/v1/auth/me", "/api/v1/auth/logout", "/api/v1/auth/change-password"}


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def client_ip(request: Request) -> str | None:
    # Nginx define X-Real-IP; solo se confía en él si la API está detrás del proxy.
    if get_settings().trust_proxy_headers and (real_ip := _valid_ip(request.headers.get("x-real-ip"))):
        return real_ip
    return _valid_ip(request.client.host if request.client else None)


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: UserSession
    ctx: RequestContext

    def has(self, permission: Permission) -> bool:
        return permission.value in self.user.permission_codes


def public_context(request: Request) -> RequestContext:
    return RequestContext(user=None, ip=client_ip(request), user_agent=request.headers.get("user-agent"))


def get_auth(
    request: Request,
    db: DbSession,
    token: Annotated[str | None, Depends(_session_cookie)],
) -> AuthContext:
    if not token:
        raise UnauthorizedError("Debe iniciar sesión.")
    user_session, user = AuthService(db).authenticate(token)
    if user.must_change_password and request.url.path not in PASSWORD_CHANGE_ALLOWED_PATHS:
        raise ForbiddenError(
            "Debe cambiar su contraseña temporal antes de continuar.", code="cambio_contrasena_requerido"
        )
    return AuthContext(
        user=user,
        session=user_session,
        ctx=RequestContext(user=user, ip=client_ip(request), user_agent=request.headers.get("user-agent")),
    )


CurrentAuth = Annotated[AuthContext, Depends(get_auth)]


def require(*permissions: Permission) -> Callable[[AuthContext], AuthContext]:
    """Exige que el usuario tenga todos los permisos indicados (403 si falta alguno)."""

    def dependency(auth: CurrentAuth) -> AuthContext:
        missing = [p.value for p in permissions if not auth.has(p)]
        if missing:
            raise ForbiddenError("No tiene permiso para realizar esta operación.", details={"requeridos": missing})
        return auth

    return dependency


def require_any(*permissions: Permission) -> Callable[[AuthContext], AuthContext]:
    """Exige al menos uno de los permisos indicados; el servicio aplica el detalle por operación."""

    def dependency(auth: CurrentAuth) -> AuthContext:
        if not any(auth.has(p) for p in permissions):
            raise ForbiddenError(
                "No tiene permiso para realizar esta operación.", details={"alguno_de": [p.value for p in permissions]}
            )
        return auth

    return dependency


def get_device(
    request: Request,
    db: DbSession,
    x_device_id: Annotated[str | None, Header()] = None,
    x_device_key: Annotated[str | None, Header()] = None,
) -> Device:
    if not x_device_id or not x_device_key:
        raise UnauthorizedError("Credenciales de dispositivo requeridas.", code="dispositivo_no_autenticado")
    return DeviceAuthService(db).authenticate(x_device_id, x_device_key, ip=client_ip(request))


CurrentDevice = Annotated[Device, Depends(get_device)]
