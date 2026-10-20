"""Traducción de errores de integridad de PostgreSQL a errores de negocio."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, ConflictError


@contextmanager
def integrity_guard(session: Session, *, duplicate_message: str = "El registro ya existe.") -> Iterator[None]:
    try:
        yield
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        sqlstate = getattr(exc.orig, "sqlstate", None)
        if sqlstate == "23505":
            raise ConflictError(duplicate_message, code="duplicado") from None
        if sqlstate == "23503":
            raise BusinessRuleError(
                "Una de las referencias indicadas no existe.", code="referencia_inexistente"
            ) from None
        raise BusinessRuleError("Los datos no cumplen las restricciones del sistema.", code="restriccion") from None
