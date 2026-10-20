"""Esquemas de autenticación, usuarios, roles, auditoría y recuperación."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.presentation.schemas.common import IPStr, ORMModel
from app.presentation.schemas.people import DegreeIn, DegreeOut, ProfileIn, ProfileOut

USERNAME_PATTERN = r"^[a-zA-Z0-9_.-]{3,64}$"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class PermissionOut(ORMModel):
    code: str
    description: str


class RoleOut(ORMModel):
    id: int
    name: str
    description: str
    is_system: bool
    permissions: list[PermissionOut]


class RoleSummary(ORMModel):
    id: int
    name: str


class RoleCreate(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9_]{3,64}$")
    description: str = Field(default="", max_length=255)
    permissions: list[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=255)
    permissions: list[str] | None = None


class UserOut(ORMModel):
    id: int
    username: str
    full_name: str = Field(description="Derivado del perfil (nombres y apellidos)")
    is_active: bool
    must_change_password: bool
    last_login_at: datetime | None
    created_at: datetime
    roles: list[RoleSummary]
    profile_complete: bool
    profile: ProfileOut | None
    degrees: list[DegreeOut]


class MeOut(UserOut):
    permissions: list[str]


class LoginResponse(BaseModel):
    """El token de sesión se entrega solo en una cookie HttpOnly (no accesible desde JavaScript)."""

    user: MeOut
    expires_at: datetime


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class UserCreate(BaseModel):
    username: str = Field(pattern=USERNAME_PATTERN)
    role_ids: list[int] = Field(min_length=1)
    password: str | None = Field(
        default=None, max_length=128, description="Si se omite, se genera una contraseña temporal."
    )
    profile: ProfileIn
    degrees: list[DegreeIn] = Field(default_factory=list, max_length=20, description="Formación académica")


class UserUpdate(BaseModel):
    role_ids: list[int] | None = Field(default=None, min_length=1)
    is_active: bool | None = None
    profile: ProfileIn | None = Field(default=None, description="Reemplaza los datos personales")
    degrees: list[DegreeIn] | None = Field(default=None, max_length=20, description="Reemplaza la lista de títulos")


class PasswordResetRequest(BaseModel):
    new_password: str | None = Field(
        default=None, max_length=128, description="Si se omite, se genera una contraseña temporal."
    )


class UserWithTemporaryPassword(BaseModel):
    user: UserOut
    temporary_password: str | None = Field(
        description="Se muestra una sola vez. Debe entregarse personalmente al usuario."
    )


class AuditLogOut(ORMModel):
    id: int
    user_id: int | None
    username: str | None = None
    action: str
    entity_type: str | None
    entity_id: str | None
    details: dict[str, Any] | None
    ip_address: IPStr
    created_at: datetime


class RecoveryRequestCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    message: str | None = Field(default=None, max_length=500)


class RecoveryRequestOut(ORMModel):
    id: int
    username_requested: str
    user_id: int | None
    user_full_name: str | None = None
    status: str
    message: str | None
    requester_ip: IPStr
    created_at: datetime
    resolved_at: datetime | None
    resolved_by_id: int | None
    resolution_note: str | None


class RecoveryApprove(BaseModel):
    identity_verified: bool = Field(description="Confirma la verificación presencial de identidad.")
    verification_note: str = Field(min_length=3, max_length=500, description="Cómo se verificó la identidad.")
    new_password: str | None = Field(default=None, max_length=128)


class RecoveryReject(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class RecoveryApprovalOut(BaseModel):
    request: RecoveryRequestOut
    temporary_password: str | None
