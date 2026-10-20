"""Punto de entrada de la API FastAPI."""

from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.presentation.api import (
    admin,
    analysis,
    auth,
    catalogs,
    health,
    incidents,
    infrastructure,
    inventory,
    measurements,
    reports,
    users,
)

API_PREFIX = "/api/v1"
# Swagger UI se sirve desde archivos locales: la documentación funciona sin Internet.
SWAGGER_DIR = Path(__file__).parent / "presentation" / "static" / "swagger"
SWAGGER_URL = f"{API_PREFIX}/docs-static"


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
        reports,
        analysis,
    ):
        api.include_router(module.router)
    app.include_router(api)
    return app


app = create_app()
