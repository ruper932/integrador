"""Esquemas del módulo provisional de estimación con el modelo de ML."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ProvisionalStationOut(BaseModel):
    device_id: int
    device_code: str
    device_name: str
    fog_collector: str | None
    mesh_area_m2: float | None
    last_seen_at: datetime | None
    estado: Literal["generada", "datos_insuficientes"]
    resultado_litros: float | None = Field(description="Volumen estimado para hoy")
    referencia_media_7d_litros: float | None = Field(description="Referencia simple: media de los últimos 7 días")
    captado_hoy_litros: float | None = Field(description="Volumen real captado hoy hasta el momento")
    variables: dict[str, float | None] = Field(description="Variables del día base usadas por el modelo")
    faltantes: list[str]


class ProvisionalPredictionOut(BaseModel):
    provisional: bool
    modelo_disponible: bool
    motivo: str | None
    version_modelo: str | None
    horizonte: str | None
    metricas_simulacion: dict[str, dict[str, float]] | None
    generado_en: datetime
    dia_base: date
    fecha_predicha: date
    estaciones: list[ProvisionalStationOut] = Field(description="Una por estación conectada; vacía si no hay ninguna")
