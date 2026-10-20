"""Endpoints de autenticación y solicitud pública de recuperación de cuenta."""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.business.services.auth_service import AuthService
from app.business.services.context import RequestContext
from app.business.services.recovery_service import PUBLIC_ACK, RecoveryService
from app.business.services.user_service import UserService
from app.core.config import get_settings
from app.data.models.security import User
from app.presentation.api.deps import CurrentAuth, DbSession, public_context
from app.presentation.schemas.common import Message
from app.presentation.schemas.people import OwnProfileUpdate
from app.presentation.schemas.security import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    MeOut,
    RecoveryRequestCreate,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["Autenticación"])

PublicContext = Annotated[RequestContext, Depends(public_context)]


def to_me(user: User) -> MeOut:
    return MeOut(**UserOut.model_validate(user).model_dump(), permissions=sorted(user.permission_codes))


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, db: DbSession, ctx: PublicContext) -> LoginResponse:
    settings = get_settings()
    result = AuthService(db).login(ctx, payload.username.strip(), payload.password)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=result.token,
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/api",
    )
    return LoginResponse(user=to_me(result.user), expires_at=result.expires_at)


@router.post("/logout", response_model=Message)
def logout(response: Response, db: DbSession, auth: CurrentAuth) -> Message:
    AuthService(db).logout(auth.ctx, auth.session)
    response.delete_cookie(get_settings().session_cookie_name, path="/api")
    return Message(message="Sesión cerrada.")


@router.get("/me", response_model=MeOut)
def me(auth: CurrentAuth) -> MeOut:
    return to_me(auth.user)


@router.put("/me/profile", response_model=MeOut, summary="Actualizar mis datos personales y formación")
def update_my_profile(payload: OwnProfileUpdate, db: DbSession, auth: CurrentAuth) -> MeOut:
    user = UserService(db).update_own_profile(
        auth.ctx,
        auth.user,
        profile=payload.profile.model_dump(),
        degrees=[d.model_dump() for d in payload.degrees],
    )
    return to_me(user)


@router.post("/change-password", response_model=Message)
def change_password(payload: ChangePasswordRequest, db: DbSession, auth: CurrentAuth) -> Message:
    AuthService(db).change_password(auth.ctx, auth.user, auth.session, payload.current_password, payload.new_password)
    return Message(message="Contraseña actualizada. Las demás sesiones fueron cerradas.")


@router.post("/recovery-requests", response_model=Message, status_code=status.HTTP_202_ACCEPTED)
def request_recovery(payload: RecoveryRequestCreate, db: DbSession, ctx: PublicContext) -> Message:
    RecoveryService(db).submit(ctx, payload.username.strip(), payload.message)
    return Message(message=PUBLIC_ACK)
