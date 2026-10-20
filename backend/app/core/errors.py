"""Errores de aplicación y su traducción a respuestas HTTP consistentes.

Formato de error:
    {"error": {"code": "...", "message": "...", "details": ...}}
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "error"

    def __init__(self, message: str, *, code: str | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        self.details = details


class BusinessRuleError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "regla_de_negocio"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "no_encontrado"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflicto"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "no_autenticado"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "sin_permiso"


class TooManyRequestsError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "demasiadas_solicitudes"


def _error_body(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_error_body(exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"loc": list(err.get("loc", [])), "msg": err.get("msg"), "type": err.get("type")} for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_body("validacion", "Los datos enviados no son válidos.", details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        messages = {404: "Recurso no encontrado.", 405: "Método no permitido."}
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body("http_error", messages.get(exc.status_code, str(exc.detail))),
        )
