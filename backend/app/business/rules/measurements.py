"""Reglas de validación de lecturas de sensores."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.data.models.iot import SensorType


class ReadingRejected(Exception):
    """La lectura no se almacena (estructura o contexto inválido)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ReadingAssessment:
    quality: str
    detail: str | None = None


def check_timestamp(measured_at: datetime, *, now: datetime, max_future_skew: timedelta) -> None:
    if measured_at.tzinfo is None:
        raise ReadingRejected("La fecha de medición debe incluir zona horaria.")
    if measured_at > now + max_future_skew:
        raise ReadingRejected("La fecha de medición está en el futuro.")


def assess_value(sensor_type: SensorType, value: float | None, unit: str) -> ReadingAssessment:
    """Clasifica la calidad de la lectura. Una variable no medida se representa como None."""
    if value is None:
        return ReadingAssessment("sin_dato")
    if math.isnan(value) or math.isinf(value):
        return ReadingAssessment("invalida", "El valor no es un número finito.")
    if unit != sensor_type.unit:
        return ReadingAssessment(
            "unidad_invalida", f"Unidad '{unit}' no corresponde; se esperaba '{sensor_type.unit}'."
        )
    if value < sensor_type.min_value or value > sensor_type.max_value:
        return ReadingAssessment(
            "fuera_de_rango",
            f"Valor {value} fuera del rango físico "
            f"[{sensor_type.min_value}, {sensor_type.max_value}] {sensor_type.unit}.",
        )
    return ReadingAssessment("valida")
