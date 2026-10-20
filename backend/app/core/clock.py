"""Fuente única de la hora actual (UTC, con zona horaria)."""

from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)
