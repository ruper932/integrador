"""Catálogos de formación académica, instituciones de egreso y cargos."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.business.services.catalog_service import CatalogService
from app.core.permissions import Permission
from app.presentation.api.deps import AuthContext, CurrentAuth, DbSession, require
from app.presentation.schemas.people import (
    AcademicLevelOut,
    InstitutionIn,
    InstitutionOut,
    InstitutionUpdate,
    PositionOut,
)

router = APIRouter(prefix="/catalogs", tags=["Catálogos"])

UserAdmin = Annotated[AuthContext, Depends(require(Permission.USERS_MANAGE))]


@router.get("/academic-levels", response_model=list[AcademicLevelOut])
def list_academic_levels(db: DbSession, _: CurrentAuth) -> list[AcademicLevelOut]:
    return [AcademicLevelOut.model_validate(x) for x in CatalogService(db).list_levels()]


@router.get("/positions", response_model=list[PositionOut])
def list_positions(db: DbSession, _: CurrentAuth) -> list[PositionOut]:
    return [PositionOut.model_validate(x) for x in CatalogService(db).list_positions()]


@router.get("/institutions", response_model=list[InstitutionOut])
def list_institutions(db: DbSession, _: CurrentAuth, include_inactive: bool = False) -> list[InstitutionOut]:
    items = CatalogService(db).list_institutions(include_inactive=include_inactive)
    return [InstitutionOut.model_validate(x) for x in items]


@router.post("/institutions", response_model=InstitutionOut, status_code=status.HTTP_201_CREATED)
def create_institution(payload: InstitutionIn, db: DbSession, auth: UserAdmin) -> InstitutionOut:
    return InstitutionOut.model_validate(CatalogService(db).create_institution(auth.ctx, payload.model_dump()))


@router.put("/institutions/{institution_id}", response_model=InstitutionOut)
def update_institution(
    institution_id: int, payload: InstitutionUpdate, db: DbSession, auth: UserAdmin
) -> InstitutionOut:
    data = payload.model_dump(exclude_unset=True)
    return InstitutionOut.model_validate(CatalogService(db).update_institution(auth.ctx, institution_id, data))
