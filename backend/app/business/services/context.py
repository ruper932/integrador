"""Contexto de la solicitud que los servicios usan para auditoría y autorización."""

from dataclasses import dataclass

from app.data.models.security import User


@dataclass(frozen=True)
class RequestContext:
    user: User | None
    ip: str | None = None
    user_agent: str | None = None

    @property
    def user_id(self) -> int | None:
        return self.user.id if self.user else None
