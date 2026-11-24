"""Preparación del conjunto diario de variables para el único modelo de predicción de volumen.

Horizonte SUPUESTO (pendiente de confirmación): predecir el volumen total captado el día D+1
con la información disponible al cierre del día D. Ninguna variable usa datos posteriores a D.

Es el mismo código para entrenar (notebooks/simulacion, que lo importa) y para estimar con datos en
vivo (API): así las variables se calculan igual en los dos casos.
"""

import numpy as np
import pandas as pd

TARGET = "volumen_dia_siguiente"
MIN_HOURLY_COVERAGE = 0.75  # un día con menos del 75 % de horas con dato no se usa como objetivo

FEATURES = [
    "volumen_dia",
    "volumen_dia_anterior",
    "volumen_media_7d",
    "humedad_media",
    "humedad_max",
    "horas_humedad_95",
    "temperatura_media",
    "temperatura_rango",
    "viento_medio",
    "presion_media",
    "presion_cambio",
    "niebla_media",
    "horas_niebla_40",
    "niebla_ultimas_6h",
    "dia_anio_sen",
    "dia_anio_cos",
]


def _hours_at_least(threshold: float):
    # Sin ninguna lectura ese día la variable no se midió: vacía, nunca 0 horas.
    return lambda s: (s >= threshold).sum() if s.notna().any() else np.nan


def build_daily(hourly: pd.DataFrame) -> pd.DataFrame:
    hourly = hourly.copy()
    hourly["measured_at"] = pd.to_datetime(hourly["measured_at"], utc=True).dt.tz_convert("America/La_Paz")
    hourly["fecha"] = hourly["measured_at"].dt.date
    groups = hourly.groupby("fecha")

    daily = pd.DataFrame(
        {
            # Volumen incremental: la suma diaria es el total captado ese día.
            "volumen_dia": groups["volumen_captado"].sum(min_count=1),
            "cobertura_volumen": groups["volumen_captado"].count() / 24,
            "humedad_media": groups["humedad_relativa"].mean(),
            "humedad_max": groups["humedad_relativa"].max(),
            "horas_humedad_95": groups["humedad_relativa"].apply(_hours_at_least(95)),
            "temperatura_media": groups["temperatura"].mean(),
            "temperatura_rango": groups["temperatura"].max() - groups["temperatura"].min(),
            "viento_medio": groups["velocidad_viento"].mean(),
            "presion_media": groups["presion_atmosferica"].mean(),
            "niebla_media": groups["niebla"].mean(),
            "horas_niebla_40": groups["niebla"].apply(_hours_at_least(40)),
            "niebla_ultimas_6h": groups["niebla"].apply(lambda s: s.tail(6).mean()),
        }
    )
    daily.index = pd.to_datetime(daily.index)
    # Un día con pocas horas de volumen no representa el total real del día.
    daily.loc[daily["cobertura_volumen"] < MIN_HOURLY_COVERAGE, "volumen_dia"] = np.nan

    daily["volumen_dia_anterior"] = daily["volumen_dia"].shift(1)
    daily["volumen_media_7d"] = daily["volumen_dia"].rolling(7, min_periods=4).mean()
    daily["presion_cambio"] = daily["presion_media"].diff()
    doy = daily.index.dayofyear
    daily["dia_anio_sen"] = np.sin(2 * np.pi * doy / 365.25)
    daily["dia_anio_cos"] = np.cos(2 * np.pi * doy / 365.25)

    # Objetivo: el volumen del día siguiente (único valor "futuro", nunca usado como entrada).
    daily[TARGET] = daily["volumen_dia"].shift(-1)
    return daily
