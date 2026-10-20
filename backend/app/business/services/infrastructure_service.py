"""Gestión de ubicaciones, atrapanieblas, tanques e invernaderos."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session

from app.business.services.audit_service import AuditService
from app.business.services.context import RequestContext
from app.business.services.integrity import integrity_guard
from app.core.errors import NotFoundError
from app.data.repositories.base import Repository
from app.data.repositories.iot import (
    FogCollectorRepository,
    GreenhouseRepository,
    LocationRepository,
    TankRepository,
)


class CatalogService:
    """CRUD con desactivación lógica y auditoría para entidades de infraestructura."""

    def __init__(self, session: Session, repo: Repository[Any], entity_type: str, label: str) -> None:
        self.session = session
        self.repo = repo
        self.entity_type = entity_type
        self.label = label
        self.audit = AuditService(session)

    def list(self, *, include_inactive: bool = False) -> Sequence[Any]:
        return self.repo.list(limit=1000, is_active=None if include_inactive else True)

    def get(self, entity_id: int) -> Any:
        entity = self.repo.get(entity_id)
        if entity is None:
            raise NotFoundError(f"{self.label} no encontrado.")
        return entity

    def create(self, ctx: RequestContext, data: dict[str, Any]) -> Any:
        with integrity_guard(self.session, duplicate_message=f"Ya existe un registro de {self.label} con ese código."):
            entity = self.repo.add(self.repo.model(**data))
        self.audit.record(ctx, f"{self.entity_type}.crear", entity_type=self.entity_type, entity_id=entity.id)
        self.session.commit()
        return entity

    def update(self, ctx: RequestContext, entity_id: int, data: dict[str, Any]) -> Any:
        entity = self.get(entity_id)
        with integrity_guard(self.session, duplicate_message=f"Ya existe un registro de {self.label} con ese código."):
            for key, value in data.items():
                setattr(entity, key, value)
        self.audit.record(
            ctx,
            f"{self.entity_type}.actualizar",
            entity_type=self.entity_type,
            entity_id=entity.id,
            details={k: str(v) for k, v in data.items()},
        )
        self.session.commit()
        return entity

    def deactivate(self, ctx: RequestContext, entity_id: int) -> Any:
        entity = self.get(entity_id)
        entity.is_active = False
        self.audit.record(ctx, f"{self.entity_type}.desactivar", entity_type=self.entity_type, entity_id=entity.id)
        self.session.commit()
        return entity


def location_service(session: Session) -> CatalogService:
    return CatalogService(session, LocationRepository(session), "location", "Ubicación")


def fog_collector_service(session: Session) -> CatalogService:
    return CatalogService(session, FogCollectorRepository(session), "fog_collector", "Atrapanieblas")


def tank_service(session: Session) -> CatalogService:
    return CatalogService(session, TankRepository(session), "tank", "Tanque")


def greenhouse_service(session: Session) -> CatalogService:
    return CatalogService(session, GreenhouseRepository(session), "greenhouse", "Invernadero")
