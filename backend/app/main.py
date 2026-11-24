"""Punto de entrada de la API FastAPI."""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.business.services.auto_incident_service import AutoIncidentService
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.data.database import SessionLocal
from app.presentation.api import (
    admin,
    analysis,
    auth,
    catalogs,
    firmware,
    health,
    incidents,
    infrastructure,
    inventory,
    measurements,
    ml,
    relocations,
    reports,
    users,
)

API_PREFIX = "/api/v1"
# Swagger UI se sirve desde archivos locales: la documentación funciona sin Internet.
SWAGGER_DIR = Path(__file__).parent / "presentation" / "static" / "swagger"
SWAGGER_URL = f"{API_PREFIX}/docs-static"

logger = logging.getLogger(__name__)


def run_auto_incidents() -> int:
    with SessionLocal() as session:
        return len(AutoIncidentService(session).run())


async def _auto_incident_loop(settings: Settings) -> None:
    """Revisión periódica dentro de la API (sin cron ni colas): estaciones sin comunicación y
    sensores con lecturas anómalas."""
    while True:
        await asyncio.sleep(settings.auto_incidents_interval_minutes * 60)
        try:
            created = await asyncio.to_thread(run_auto_incidents)
            if created:
                logger.info("Incidencias automáticas abiertas: %s", created)
        except Exception:
            # Un fallo puntual (p. ej. la base reiniciándose) no debe detener la API ni el ciclo.
            logger.exception("Falló la revisión de incidencias automáticas")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    task = None
    if settings.auto_incidents_enabled and settings.environment != "test":
        task = asyncio.create_task(_auto_incident_loop(settings))
    yield
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "API local para el monitoreo de agua captada mediante atrapanieblas — "
            "CEA “Ildefonso de las Muñecas”, Titicachi, Chuma, La Paz."
        ),
        docs_url=None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
        lifespan=lifespan,
    )
    app.mount(SWAGGER_URL, StaticFiles(directory=SWAGGER_DIR), name="swagger")

    @app.get("/docs", include_in_schema=False)
    def swagger_ui() -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url=app.openapi_url or "",
            title=f"{settings.app_name} — API",
            swagger_js_url=f"{SWAGGER_URL}/swagger-ui-bundle.js",
            swagger_css_url=f"{SWAGGER_URL}/swagger-ui.css",
            swagger_favicon_url="data:,",
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-Device-Id", "X-Device-Key"],
    )
    register_exception_handlers(app)

    api = APIRouter(prefix=API_PREFIX)
    for module in (
        health,
        auth,
        admin,
        users,
        catalogs,
        infrastructure,
        measurements,
        inventory,
        incidents,
        relocations,
        reports,
        analysis,
        firmware,
        ml,
    ):
        api.include_router(module.router)
    app.include_router(api)
    return app


app = create_app()
