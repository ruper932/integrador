"""Repositorios de usuarios, roles, sesiones, auditoría y recuperación de cuenta."""

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update

from app.data.models.people import UserProfile
from app.data.models.security import (
    AccountRecoveryRequest,
    AuditLog,
    Permission,
    Role,
    User,
    UserSession,
)
from app.data.repositories.base import Repository


class UserRepository(Repository[User]):
    model = User

    def get_by_username(self, username: str) -> User | None:
        return self.session.scalars(select(User).where(func.lower(User.username) == username.lower())).first()

    def search(
        self,
        *,
        offset: int,
        limit: int,
        is_active: bool | None = None,
        q: str | None = None,
        role_id: int | None = None,
        position_id: int | None = None,
    ) -> tuple[Sequence[User], int]:
        stmt = select(User).order_by(User.username)
        if is_active is not None:
            stmt = stmt.where(User.is_active.is_(is_active))
        if role_id is not None:
            stmt = stmt.where(User.roles.any(Role.id == role_id))
        if position_id is not None:
            stmt = stmt.where(User.profile.has(UserProfile.position_id == position_id))
        if q:
            pattern = f"%{q.lower()}%"
            person = func.concat_ws(
                " ", UserProfile.first_names, UserProfile.paternal_surname, UserProfile.maternal_surname
            )
            stmt = stmt.outerjoin(UserProfile, UserProfile.user_id == User.id).where(
                func.lower(User.username).like(pattern)
                | func.lower(person).like(pattern)
                | UserProfile.ci_number.like(f"%{q}%")
            )
        return self.paginate(stmt, offset=offset, limit=limit)

    def active_with_permission(self, code: str) -> Sequence[User]:
        return self.with_any_permission([code], active_only=True)

    def with_any_permission(self, codes: Sequence[str], *, active_only: bool) -> Sequence[User]:
        holders = select(User.id).join(User.roles).join(Role.permissions).where(Permission.code.in_(codes))
        stmt = select(User).where(User.id.in_(holders)).order_by(User.id)
        if active_only:
            stmt = stmt.where(User.is_active.is_(True))
        return self.session.scalars(stmt).unique().all()


class RoleRepository(Repository[Role]):
    model = Role

    def get_many_by_ids(self, ids: Sequence[int]) -> Sequence[Role]:
        return self.session.scalars(select(Role).where(Role.id.in_(ids))).all()

    def get_by_name(self, name: str) -> Role | None:
        return self.session.scalars(select(Role).where(Role.name == name)).first()


class PermissionRepository(Repository[Permission]):
    model = Permission

    def get_many_by_codes(self, codes: Sequence[str]) -> Sequence[Permission]:
        return self.session.scalars(select(Permission).where(Permission.code.in_(codes))).all()


class UserSessionRepository(Repository[UserSession]):
    model = UserSession

    def get_active_by_token_hash(self, token_hash: str, now: datetime) -> UserSession | None:
        stmt = select(UserSession).where(
            UserSession.token_hash == token_hash,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
        return self.session.scalars(stmt).first()

    def revoke_all_for_user(self, user_id: int, now: datetime, *, except_id: int | None = None) -> None:
        stmt = update(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        if except_id is not None:
            stmt = stmt.where(UserSession.id != except_id)
        self.session.execute(stmt.values(revoked_at=now))


class AuditLogRepository(Repository[AuditLog]):
    model = AuditLog

    def count_since(self, *, action: str, ip: str, since: datetime) -> int:
        stmt = select(func.count()).where(
            AuditLog.action == action, AuditLog.ip_address == ip, AuditLog.created_at >= since
        )
        return self.session.scalar(stmt) or 0

    def distinct_actions(self) -> Sequence[str]:
        return self.session.scalars(select(AuditLog.action).distinct().order_by(AuditLog.action)).all()

    def search(
        self,
        *,
        offset: int,
        limit: int,
        user_id: int | None = None,
        action: str | None = None,
        entity_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[Sequence[AuditLog], int]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        filters: list[Any] = []
        if user_id is not None:
            filters.append(AuditLog.user_id == user_id)
        if action:
            # Una acción completa («usuario.crear») o su módulo («usuario»).
            filters.append((AuditLog.action == action) if "." in action else AuditLog.action.startswith(f"{action}."))
        if entity_type:
            filters.append(AuditLog.entity_type == entity_type)
        if date_from:
            filters.append(AuditLog.created_at >= date_from)
        if date_to:
            filters.append(AuditLog.created_at <= date_to)
        return self.paginate(stmt.where(*filters), offset=offset, limit=limit)


class RecoveryRequestRepository(Repository[AccountRecoveryRequest]):
    model = AccountRecoveryRequest

    def count_by_ip_since(self, ip: str, since: datetime) -> int:
        stmt = select(func.count()).where(
            AccountRecoveryRequest.requester_ip == ip, AccountRecoveryRequest.created_at >= since
        )
        return self.session.scalar(stmt) or 0

    def count_by_username_since(self, username: str, since: datetime) -> int:
        stmt = select(func.count()).where(
            func.lower(AccountRecoveryRequest.username_requested) == username.lower(),
            AccountRecoveryRequest.created_at >= since,
        )
        return self.session.scalar(stmt) or 0

    def search(self, *, offset: int, limit: int, status: str | None) -> tuple[Sequence[AccountRecoveryRequest], int]:
        stmt = select(AccountRecoveryRequest).order_by(AccountRecoveryRequest.created_at.desc())
        if status:
            stmt = stmt.where(AccountRecoveryRequest.status == status)
        return self.paginate(stmt, offset=offset, limit=limit)
