"""Análisis estadístico de la información de los módulos."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import AwareDatetime

from app.business.services.analysis_service import AnalysisService
from app.core.permissions import Permission
from app.presentation.api.deps import AuthContext, DbSession, require

router = APIRouter(tags=["Análisis estadístico"])

# El análisis reúne información de varios módulos: lo consulta quien puede generar reportes
# (director y administrador); cada sección exige además el permiso de su módulo.
Analyst = Annotated[AuthContext, Depends(require(Permission.REPORTS_GENERATE))]


@router.get("/analysis", summary="Indicadores estadísticos del periodo (captación, variables, calidad, operación)")
def analysis(
    db: DbSession,
    auth: Analyst,
    date_from: AwareDatetime | None = None,
    date_to: AwareDatetime | None = None,
    device_id: int | None = None,
    fog_collector_id: int | None = None,
) -> dict[str, Any]:  # shortcut: respuesta sin esquema Pydantic propio; tiparla si otro cliente la consume.
    return AnalysisService(db).analyze(
        auth.ctx, date_from=date_from, date_to=date_to, device_id=device_id, fog_collector_id=fog_collector_id
    )
