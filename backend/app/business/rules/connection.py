"""Regla única de conexión de las estaciones, usada por todos los módulos.

Una estación envía sus lecturas en cada muestreo (cada `sample_interval_s`, que fija el sistema). Se
considera que perdió la conexión cuando pasan tres intervalos más un margen de 60 s sin que se comunique;
`DEVICE_STALE_MINUTES` es el tope (y el valor para una estación sin intervalo conocido). Así se detecta en
pocos minutos tanto en Monitoreo como en Dispositivos, el resumen, Atrapanieblas o los reportes.
"""

from datetime import datetime, timedelta

from app.core.config import get_settings

MISSED_INTERVALS = 3
GRACE_SECONDS = 60

CONNECTION_LABELS = {"al_dia": "Al día", "desactualizado": "Desactualizado", "sin_comunicacion": "Sin comunicación"}


def stale_after(sample_interval_s: int | None) -> timedelta:
    limit = timedelta(minutes=get_settings().device_stale_minutes)
    if not sample_interval_s:
        return limit
    return min(limit, timedelta(seconds=MISSED_INTERVALS * sample_interval_s + GRACE_SECONDS))


def is_stale(last_seen_at: datetime | None, sample_interval_s: int | None, now: datetime) -> bool:
    return last_seen_at is None or now - last_seen_at > stale_after(sample_interval_s)


def connection_state(last_seen_at: datetime | None, sample_interval_s: int | None, now: datetime) -> str:
    if last_seen_at is None:
        return "sin_comunicacion"
    return "desactualizado" if is_stale(last_seen_at, sample_interval_s, now) else "al_dia"
