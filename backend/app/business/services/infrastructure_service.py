"""Gestión de ubicaciones, atrapanieblas, tanques e invernaderos."""

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from sqlalchemy.orm import Session

from app.business.services.audit_service import AuditService
from app.business.services.context import RequestContext
from app.business.services.integrity import integrity_guard
from app.business.services.user_service import local_today
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.data.repositories.base import Repository
from app.data.repositories.iot import (
    FogCollectorRepository,
    GreenhouseRepository,
    LocationRepository,
    TankRepository,
)
from app.data.repositories.relocations import RelocationRepository

# Revisa la entidad ya con los cambios aplicados (reglas que combinan varios campos).
Check = Callable[[Any], None]
# Revisa un cambio antes de aplicarlo: (entidad actual, datos nuevos).
Guard = Callable[[Any, Mapping[str, Any]], None]


class CatalogService:
    """CRUD con desactivación lógica y auditoría para entidades de infraestructura."""

    def __init__(
        self,
        session: Session,
        repo: Repository[Any],
        entity_type: str,
        label: str,
        *,
        refs: Mapping[str, tuple[Repository[Any], str]] | None = None,
        check: Check | None = None,
        guard: Guard | None = None,
    ) -> None:
        self.session = session
        self.repo = repo
        self.entity_type = entity_type
        self.label = label
        # Campo → (repositorio, descripción): la referencia debe existir y estar activa.
        self.refs = refs or {}
        self.check = check
        self.guard = guard
        self.audit = AuditService(session)

    def _check_refs(self, data: Mapping[str, Any], entity: Any = None) -> None:
        for field, (repo, description) in self.refs.items():
            value = data.get(field)
            # Una referencia que no cambia se conserva aunque luego se haya desactivado.
            if value is None or (entity is not None and getattr(entity, field) == value):
                continue
            ref = repo.get(value)
            if ref is None or not ref.is_active:
                raise BusinessRuleError(f"{description} no existe o está desactivado.", code="referencia_invalida")

    def list(self, *, include_inactive: bool = False) -> Sequence[Any]:
        return self.repo.list(limit=1000, is_active=None if include_inactive else True)

    def get(self, entity_id: int) -> Any:
        entity = self.repo.get(entity_id)
        if entity is None:
            raise NotFoundError(f"{self.label} no encontrado.")
        return entity

    def create(self, ctx: RequestContext, data: dict[str, Any]) -> Any:
        self._check_refs(data)
        candidate = self.repo.model(**data)
        if self.check:
            self.check(candidate)
        with integrity_guard(self.session, duplicate_message=f"Ya existe un registro de {self.label} con ese código."):
            entity = self.repo.add(candidate)
        self.audit.record(ctx, f"{self.entity_type}.crear", entity_type=self.entity_type, entity_id=entity.id)
        self.session.commit()
        return entity

    def update(self, ctx: RequestContext, entity_id: int, data: dict[str, Any]) -> Any:
        entity = self.get(entity_id)
        if self.guard:
            self.guard(entity, data)
        self._check_refs(data, entity)
        with integrity_guard(self.session, duplicate_message=f"Ya existe un registro de {self.label} con ese código."):
            for key, value in data.items():
                setattr(entity, key, value)
            if self.check:
                self.check(entity)
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
        if self.guard:
            self.guard(entity, {"is_active": False})
        entity.is_active = False
        self.audit.record(ctx, f"{self.entity_type}.desactivar", entity_type=self.entity_type, entity_id=entity.id)
        self.session.commit()
        return entity


def _coordinates_pair(location: Any) -> None:
    if (location.latitude is None) != (location.longitude is None):
        raise BusinessRuleError("Indique la latitud y la longitud juntas, o ninguna.", code="coordenadas_incompletas")


def _not_installed_in_future(fog_collector: Any) -> None:
    if fog_collector.installed_on is not None and fog_collector.installed_on > local_today():
        raise BusinessRuleError("La fecha de instalación no puede estar en el futuro.", code="fecha_futura")


def location_service(session: Session) -> CatalogService:
    return CatalogService(session, LocationRepository(session), "location", "Ubicación", check=_coordinates_pair)


def fog_collector_service(session: Session) -> CatalogService:
    relocations = RelocationRepository(session)

    def guard(fog_collector: Any, data: Mapping[str, Any]) -> None:
        moves = "location_id" in data and data["location_id"] != fog_collector.location_id
        if (moves or data.get("is_active") is False) and (active := relocations.active_for(fog_collector.id)):
            # El traslado lo registra la solicitud en curso; un cambio directo la contradiría.
            raise ConflictError(
                f"El atrapanieblas tiene una solicitud de reubicación en curso (#{active.id}); "
                "la ubicación cambia al finalizarla.",
                code="reubicacion_en_curso",
            )

    return CatalogService(
        session,
        FogCollectorRepository(session),
        "fog_collector",
        "Atrapanieblas",
        refs={"location_id": (LocationRepository(session), "La ubicación indicada")},
        check=_not_installed_in_future,
        guard=guard,
    )


def tank_service(session: Session) -> CatalogService:
    return CatalogService(
        session,
        TankRepository(session),
        "tank",
        "Tanque",
        refs={
            "location_id": (LocationRepository(session), "La ubicación indicada"),
            "fog_collector_id": (FogCollectorRepository(session), "El atrapanieblas indicado"),
        },
    )


def greenhouse_service(session: Session) -> CatalogService:
    return CatalogService(
        session,
        GreenhouseRepository(session),
        "greenhouse",
        "Invernadero",
        refs={
            "location_id": (LocationRepository(session), "La ubicación indicada"),
            "tank_id": (TankRepository(session), "El tanque indicado"),
        },
    )
