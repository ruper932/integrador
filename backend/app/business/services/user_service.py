"""Gestión de usuarios y roles."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.business.rules.passwords import validate_password_policy
from app.business.rules.people import (
    DegreeTimeline,
    normalize_profile,
    profile_changes,
    validate_birth_date,
    validate_degree_ages,
)
from app.business.services.audit_service import AuditService
from app.business.services.context import RequestContext
from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.core.permissions import ROLE_ADMIN
from app.core.security import generate_temporary_password, hash_password
from app.data.models.people import UserDegree, UserProfile
from app.data.models.security import Permission, Role, User
from app.data.repositories.people import (
    AcademicLevelRepository,
    InstitutionRepository,
    PositionRepository,
    UserProfileRepository,
)
from app.data.repositories.security import (
    PermissionRepository,
    RoleRepository,
    UserRepository,
    UserSessionRepository,
)


def local_today() -> date:
    return utcnow().astimezone(ZoneInfo(get_settings().local_timezone)).date()


@dataclass(frozen=True)
class UserWithPassword:
    user: User
    temporary_password: str | None


class UserService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.roles = RoleRepository(session)
        self.sessions = UserSessionRepository(session)
        self.profiles = UserProfileRepository(session)
        self.levels = AcademicLevelRepository(session)
        self.institutions = InstitutionRepository(session)
        self.positions = PositionRepository(session)
        self.audit = AuditService(session)

    def list(self, *, offset: int, limit: int, is_active: bool | None, q: str | None) -> tuple[Sequence[User], int]:
        return self.users.search(offset=offset, limit=limit, is_active=is_active, q=q)

    def get(self, user_id: int) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError("Usuario no encontrado.")
        return user

    def _resolve_roles(self, role_ids: Sequence[int]) -> list[Role]:
        unique_ids = sorted(set(role_ids))
        roles = list(self.roles.get_many_by_ids(unique_ids))
        if len(roles) != len(unique_ids):
            raise BusinessRuleError("Uno o más roles indicados no existen.", code="rol_inexistente")
        if not roles:
            raise BusinessRuleError("El usuario debe tener al menos un rol.", code="rol_requerido")
        return roles

    def create(
        self,
        ctx: RequestContext,
        *,
        username: str,
        role_ids: Sequence[int],
        profile: dict[str, Any],
        degrees: Sequence[dict[str, Any]] = (),
        password: str | None = None,
    ) -> UserWithPassword:
        if self.users.get_by_username(username):
            raise ConflictError("Ya existe un usuario con ese nombre de usuario.", code="usuario_duplicado")
        roles = self._resolve_roles(role_ids)
        profile = self._validate_profile(normalize_profile(profile), user_id=None)
        degree_rows = self._validate_degrees(degrees, profile.get("birth_date"))
        temporary = None
        if password is None:
            temporary = generate_temporary_password()
            password = temporary
        else:
            validate_password_policy(password, username=username)
        user = self.users.add(
            User(
                username=username,
                password_hash=hash_password(password),
                is_active=True,
                # El usuario siempre define su propia contraseña en el primer inicio de sesión.
                must_change_password=True,
                failed_login_attempts=0,
                roles=roles,
                profile=UserProfile(**profile),
                degrees=degree_rows,
            )
        )
        self.audit.record(
            ctx,
            "usuario.crear",
            entity_type="user",
            entity_id=user.id,
            details={"username": username, "roles": [r.name for r in roles], "titulos": len(degree_rows)},
        )
        self.session.commit()
        return UserWithPassword(user=user, temporary_password=temporary)

    # --- Perfil y formación ---------------------------------------------------

    def _validate_profile(self, data: dict[str, Any], *, user_id: int | None) -> dict[str, Any]:
        if not (data.get("paternal_surname") or data.get("maternal_surname")):
            raise BusinessRuleError("Indique al menos un apellido.", code="apellido_requerido")
        if data.get("birth_date") is not None:
            validate_birth_date(data["birth_date"], local_today())
        if data.get("ci_number"):
            other = self.profiles.find_by_ci(data["ci_number"], data.get("ci_complement"))
            if other is not None and other.user_id != user_id:
                raise ConflictError("Ya existe un usuario registrado con ese número de CI.", code="ci_duplicado")
        if data.get("institutional_email"):
            other = self.profiles.find_by_institutional_email(data["institutional_email"])
            if other is not None and other.user_id != user_id:
                raise ConflictError("El correo institucional ya está registrado.", code="correo_duplicado")
        if data.get("position_id") is not None:
            position = self.positions.get(data["position_id"])
            if position is None or not position.is_active:
                raise BusinessRuleError("El cargo indicado no existe.", code="cargo_invalido")
        return data

    def _validate_degrees(self, degrees: Sequence[dict[str, Any]], birth_date: date | None) -> list[UserDegree]:
        rows: list[UserDegree] = []
        timeline: list[DegreeTimeline] = []
        for degree in degrees:
            level = self.levels.get(degree["academic_level_id"])
            if level is None:
                raise BusinessRuleError("El nivel académico indicado no existe.", code="nivel_invalido")
            timeline.append(DegreeTimeline(level.name, level.min_graduation_age, degree.get("graduation_year")))
            institution = self.institutions.get(degree["institution_id"])
            if institution is None or not institution.is_active:
                raise BusinessRuleError("La institución de egreso indicada no existe.", code="institucion_invalida")
            rows.append(
                UserDegree(
                    academic_level_id=degree["academic_level_id"],
                    title=" ".join(degree["title"].split()),
                    institution_id=degree["institution_id"],
                    graduation_year=degree.get("graduation_year"),
                )
            )
        validate_degree_ages(birth_date, timeline)
        return rows

    @staticmethod
    def _check_existing_degrees(user: User) -> None:
        """Al cambiar la fecha de nacimiento, los títulos ya registrados deben seguir siendo coherentes."""
        validate_degree_ages(
            user.profile.birth_date if user.profile else None,
            [
                DegreeTimeline(d.academic_level.name, d.academic_level.min_graduation_age, d.graduation_year)
                for d in user.degrees
            ],
        )

    def _apply_profile(self, user: User, data: dict[str, Any]) -> list[str]:
        data = self._validate_profile(normalize_profile(data), user_id=user.id)
        if user.profile is None:
            user.profile = UserProfile(**data)
            return sorted(data)
        current = {key: getattr(user.profile, key) for key in data}
        changed = profile_changes(current, data)
        for key in changed:
            setattr(user.profile, key, data[key])
        return changed

    def _ensure_admin_remains(self, user: User, *, will_be_active: bool, will_have_roles: Sequence[Role]) -> None:
        is_admin_now = user.is_active and any(r.name == ROLE_ADMIN for r in user.roles)
        stays_admin = will_be_active and any(r.name == ROLE_ADMIN for r in will_have_roles)
        if is_admin_now and not stays_admin:
            active_admins = [
                u for u in self.users.list(limit=10_000, is_active=True) if any(r.name == ROLE_ADMIN for r in u.roles)
            ]
            if len(active_admins) <= 1:
                raise BusinessRuleError(
                    "No se puede dejar el sistema sin administradores activos.", code="ultimo_administrador"
                )

    def update(
        self,
        ctx: RequestContext,
        user_id: int,
        *,
        role_ids: Sequence[int] | None = None,
        is_active: bool | None = None,
        profile: dict[str, Any] | None = None,
        degrees: Sequence[dict[str, Any]] | None = None,
    ) -> User:
        user = self.get(user_id)
        changes: dict[str, object] = {}
        new_roles = self._resolve_roles(role_ids) if role_ids is not None else list(user.roles)
        new_active = user.is_active if is_active is None else is_active
        if ctx.user_id == user.id and not new_active:
            raise BusinessRuleError("No puede desactivar su propia cuenta.", code="autodesactivacion")
        self._ensure_admin_remains(user, will_be_active=new_active, will_have_roles=new_roles)

        # Solo se audita qué campos del perfil cambiaron, no los datos personales.
        if profile is not None and (changed := self._apply_profile(user, profile)):
            changes["perfil"] = changed
        birth_date = user.profile.birth_date if user.profile else None
        if degrees is not None:
            user.degrees = self._validate_degrees(degrees, birth_date)
            changes["titulos"] = len(user.degrees)
        elif profile is not None:
            self._check_existing_degrees(user)
        if role_ids is not None and {r.id for r in new_roles} != {r.id for r in user.roles}:
            changes["roles"] = [r.name for r in new_roles]
            user.roles = new_roles
        if new_active != user.is_active:
            changes["is_active"] = new_active
            user.is_active = new_active
            if not new_active:
                self.sessions.revoke_all_for_user(user.id, utcnow())
        if changes:
            self.audit.record(ctx, "usuario.actualizar", entity_type="user", entity_id=user.id, details=changes)
        self.session.commit()
        return user

    def update_own_profile(
        self, ctx: RequestContext, user: User, *, profile: dict[str, Any], degrees: Sequence[dict[str, Any]]
    ) -> User:
        """El usuario autenticado actualiza sus datos personales y su formación.

        No puede modificar su usuario, roles, estado ni cargo: esos datos los administra el
        administrador. Por eso `position_id` se descarta aunque llegue en la solicitud.
        """
        data = {key: value for key, value in profile.items() if key != "position_id"}
        changes: dict[str, object] = {}
        if changed := self._apply_profile(user, data):
            changes["perfil"] = changed
        new_degrees = self._validate_degrees(degrees, user.profile.birth_date if user.profile else None)
        current = [(d.academic_level_id, d.title, d.institution_id, d.graduation_year) for d in user.degrees]
        proposed = [(d.academic_level_id, d.title, d.institution_id, d.graduation_year) for d in new_degrees]
        if current != proposed:
            user.degrees = new_degrees
            changes["titulos"] = len(new_degrees)
        if changes:
            self.audit.record(ctx, "perfil.actualizar_propio", entity_type="user", entity_id=user.id, details=changes)
        self.session.commit()
        self.session.refresh(user)
        return user

    def deactivate(self, ctx: RequestContext, user_id: int) -> User:
        return self.update(ctx, user_id, is_active=False)

    def reset_password(self, ctx: RequestContext, user_id: int, new_password: str | None = None) -> UserWithPassword:
        user = self.get(user_id)
        temporary = self.apply_password_reset(user, new_password)
        self.audit.record(ctx, "usuario.restablecer_contrasena", entity_type="user", entity_id=user.id)
        self.session.commit()
        return UserWithPassword(user=user, temporary_password=temporary)

    def apply_password_reset(self, user: User, new_password: str | None) -> str | None:
        """Asigna una contraseña nueva o temporal e invalida las sesiones activas (sin commit)."""
        temporary = None
        if new_password is None:
            temporary = generate_temporary_password()
            new_password = temporary
        else:
            validate_password_policy(new_password, username=user.username)
        now = utcnow()
        user.password_hash = hash_password(new_password)
        user.must_change_password = True
        user.password_changed_at = now
        user.failed_login_attempts = 0
        user.locked_until = None
        self.sessions.revoke_all_for_user(user.id, now)
        return temporary


class RoleService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.roles = RoleRepository(session)
        self.permissions = PermissionRepository(session)
        self.audit = AuditService(session)

    def list_roles(self) -> Sequence[Role]:
        return self.roles.list(limit=1000, order_by=Role.name)

    def list_permissions(self) -> Sequence[Permission]:
        return self.permissions.list(limit=1000)

    def create(self, ctx: RequestContext, *, name: str, description: str, permission_codes: Sequence[str]) -> Role:
        if self.roles.get_by_name(name):
            raise ConflictError("Ya existe un rol con ese nombre.", code="rol_duplicado")
        role = self.roles.add(
            Role(name=name, description=description, is_system=False, permissions=self._perms(permission_codes))
        )
        self.audit.record(
            ctx, "rol.crear", entity_type="role", entity_id=role.id, details={"permisos": list(permission_codes)}
        )
        self.session.commit()
        return role

    def update(
        self,
        ctx: RequestContext,
        role_id: int,
        *,
        description: str | None = None,
        permission_codes: Sequence[str] | None = None,
    ) -> Role:
        role = self.roles.get(role_id)
        if role is None:
            raise NotFoundError("Rol no encontrado.")
        if permission_codes is not None:
            if role.name == ROLE_ADMIN:
                raise BusinessRuleError(
                    "Los permisos del rol administrador no pueden modificarse.", code="rol_protegido"
                )
            role.permissions = self._perms(permission_codes)
        if description is not None:
            role.description = description
        self.audit.record(
            ctx,
            "rol.actualizar",
            entity_type="role",
            entity_id=role.id,
            details={"permisos": list(permission_codes) if permission_codes is not None else None},
        )
        self.session.commit()
        return role

    def _perms(self, codes: Sequence[str]) -> list[Permission]:
        unique = sorted(set(codes))
        perms = list(self.permissions.get_many_by_codes(unique))
        if len(perms) != len(unique):
            raise BusinessRuleError("Uno o más permisos indicados no existen.", code="permiso_inexistente")
        return perms
