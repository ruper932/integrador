"""Catálogos de formación académica y cargos."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session

from app.business.services.audit_service import AuditService
from app.business.services.context import RequestContext
from app.business.services.integrity import integrity_guard
from app.core.errors import ConflictError, NotFoundError
from app.data.models.people import AcademicLevel, Institution, Position
from app.data.repositories.people import AcademicLevelRepository, InstitutionRepository, PositionRepository


class CatalogService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.levels = AcademicLevelRepository(session)
        self.institutions = InstitutionRepository(session)
        self.positions = PositionRepository(session)
        self.audit = AuditService(session)

    def list_levels(self) -> Sequence[AcademicLevel]:
        return self.levels.list(limit=100, order_by=AcademicLevel.sort_order)

    def list_positions(self) -> Sequence[Position]:
        return self.positions.list(limit=100, is_active=True, order_by=Position.id)

    def list_institutions(self, *, include_inactive: bool = False) -> Sequence[Institution]:
        return self.institutions.list(
            limit=1000, order_by=Institution.name, is_active=None if include_inactive else True
        )

    def create_institution(self, ctx: RequestContext, data: dict[str, Any]) -> Institution:
        data = {**data, "name": " ".join(data["name"].split())}
        if self.institutions.get_by_name(data["name"]):
            raise ConflictError("La institución ya está registrada.", code="institucion_duplicada")
        with integrity_guard(self.session, duplicate_message="La institución ya está registrada."):
            institution = self.institutions.add(Institution(is_active=True, **data))
        self.audit.record(ctx, "catalogo.institucion_crear", entity_type="institution", entity_id=institution.id)
        self.session.commit()
        return institution

    def update_institution(self, ctx: RequestContext, institution_id: int, data: dict[str, Any]) -> Institution:
        institution = self.institutions.get(institution_id)
        if institution is None:
            raise NotFoundError("Institución no encontrada.")
        with integrity_guard(self.session, duplicate_message="La institución ya está registrada."):
            for key, value in data.items():
                setattr(institution, key, value)
        self.audit.record(
            ctx, "catalogo.institucion_actualizar", entity_type="institution", entity_id=institution.id, details=data
        )
        self.session.commit()
        return institution
