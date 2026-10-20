"""Endpoints de salud del servicio."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.business.services.health_service import HealthService
from app.presentation.api.deps import DbSession

router = APIRouter(prefix="/health", tags=["Salud"])


@router.get("")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/db")
def health_db(db: DbSession) -> JSONResponse:
    if not HealthService(db).database_available():
        # No se exponen detalles de conexión.
        return JSONResponse(status_code=503, content={"status": "error", "database": "no disponible"})
    return JSONResponse(content={"status": "ok", "database": "disponible"})
