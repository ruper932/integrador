"""Inferencia con el artefacto del modelo: nunca inventa una predicción.

Devuelve fecha, variables usadas, resultado, versión del modelo y estado; informa
`datos_insuficientes` cuando faltan variables clave (compartido con notebooks/simulacion).
"""

import pandas as pd

# Variables sin las cuales no se predice: el volumen del día y la humedad.
REQUIRED = ("volumen_dia", "humedad_media")
MAX_MISSING_FRACTION = 0.3


def predict(artifact: dict, row: pd.Series, target_date: str) -> dict:
    features: list[str] = artifact["features"]
    values = {f: (None if pd.isna(row.get(f)) else round(float(row[f]), 3)) for f in features}
    missing = [f for f, v in values.items() if v is None]
    base = {
        "fecha_predicha": target_date,
        "version_modelo": artifact["metadata"]["version_modelo"],
        "variables": values,
    }
    if any(values[f] is None for f in REQUIRED) or len(missing) / len(features) > MAX_MISSING_FRACTION:
        return {**base, "estado": "datos_insuficientes", "resultado_litros": None, "faltantes": missing}
    estimate = float(artifact["model"].predict(pd.DataFrame([row[features]]))[0])
    return {**base, "estado": "generada", "resultado_litros": round(max(0.0, estimate), 2)}
