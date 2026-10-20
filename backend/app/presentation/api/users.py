"""Endpoints de usuarios y roles."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.business.services.user_service import RoleService, UserService
from app.core.permissions import Permission
from app.presentation.api.deps import AuthContext, DbSession, require
from app.presentation.schemas.common import Page
from app.presentation.schemas.security import (
    PasswordResetRequest,
    PermissionOut,
    RoleCreate,
    RoleOut,
    RoleUpdate,
    UserCreate,
    UserOut,
    UserUpdate,
    UserWithTemporaryPassword,
)

router = APIRouter(tags=["Usuarios y roles"])

UserAdmin = Annotated[AuthContext, Depends(require(Permission.USERS_MANAGE))]
RoleAdmin = Annotated[AuthContext, Depends(require(Permission.ROLES_MANAGE))]


@router.get("/users", response_model=Page[UserOut])
def list_users(
    db: DbSession,
    _: UserAdmin,
    q: str | None = None,
    is_active: bool | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Page[UserOut]:
    items, total = UserService(db).list(offset=offset, limit=limit, is_active=is_active, q=q)
    return Page(items=[UserOut.model_validate(u) for u in items], total=total, offset=offset, limit=limit)


@router.post("/users", response_model=UserWithTemporaryPassword, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: DbSession, auth: UserAdmin) -> UserWithTemporaryPassword:
    result = UserService(db).create(
        auth.ctx,
        username=payload.username,
        role_ids=payload.role_ids,
        password=payload.password,
        profile=payload.profile.model_dump(),
        degrees=[d.model_dump() for d in payload.degrees],
    )
    return UserWithTemporaryPassword(
        user=UserOut.model_validate(result.user), temporary_password=result.temporary_password
    )


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: DbSession, _: UserAdmin) -> UserOut:
    return UserOut.model_validate(UserService(db).get(user_id))


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, payload: UserUpdate, db: DbSession, auth: UserAdmin) -> UserOut:
    user = UserService(db).update(
        auth.ctx,
        user_id,
        role_ids=payload.role_ids,
        is_active=payload.is_active,
        profile=payload.profile.model_dump() if payload.profile else None,
        degrees=[d.model_dump() for d in payload.degrees] if payload.degrees is not None else None,
    )
    return UserOut.model_validate(user)


@router.delete("/users/{user_id}", response_model=UserOut, summary="Desactivar usuario (no se elimina)")
def deactivate_user(user_id: int, db: DbSession, auth: UserAdmin) -> UserOut:
    return UserOut.model_validate(UserService(db).deactivate(auth.ctx, user_id))


@router.post("/users/{user_id}/reset-password", response_model=UserWithTemporaryPassword)
def reset_password(
    user_id: int, payload: PasswordResetRequest, db: DbSession, auth: UserAdmin
) -> UserWithTemporaryPassword:
    result = UserService(db).reset_password(auth.ctx, user_id, payload.new_password)
    return UserWithTemporaryPassword(
        user=UserOut.model_validate(result.user), temporary_password=result.temporary_password
    )


@router.get("/roles", response_model=list[RoleOut])
def list_roles(db: DbSession, _: UserAdmin) -> list[RoleOut]:
    return [RoleOut.model_validate(r) for r in RoleService(db).list_roles()]


@router.post("/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(payload: RoleCreate, db: DbSession, auth: RoleAdmin) -> RoleOut:
    role = RoleService(db).create(
        auth.ctx, name=payload.name, description=payload.description, permission_codes=payload.permissions
    )
    return RoleOut.model_validate(role)


@router.put("/roles/{role_id}", response_model=RoleOut)
def update_role(role_id: int, payload: RoleUpdate, db: DbSession, auth: RoleAdmin) -> RoleOut:
    role = RoleService(db).update(
        auth.ctx, role_id, description=payload.description, permission_codes=payload.permissions
    )
    return RoleOut.model_validate(role)


@router.get("/permissions", response_model=list[PermissionOut])
def list_permissions(db: DbSession, _: RoleAdmin) -> list[PermissionOut]:
    return [PermissionOut.model_validate(p) for p in RoleService(db).list_permissions()]
