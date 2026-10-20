"""Paso 4 — Inferencia de ejemplo con el artefacto de la simulación.

Muestra el comportamiento previsto para el futuro servicio de predicción:
- Informa explícitamente cuando no hay datos suficientes (no inventa una predicción).
- Devuelve fecha, variables usadas, resultado, versión del modelo y estado.
"""

import json
import math
from pathlib import Path

import joblib
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


def main(output_dir: Path) -> list[dict]:
    artifact = joblib.load(next(output_dir.glob("modelo_*.joblib")))
    data = pd.read_csv(output_dir / "dataset_diario.csv", index_col="fecha", parse_dates=True)
    last = data.iloc[-1]
    examples = [predict(artifact, last, str((data.index[-1] + pd.Timedelta(days=1)).date()))]
    incomplete = last.copy()
    incomplete["volumen_dia"] = math.nan  # p. ej., el sensor de volumen falló todo el día
    examples.append(predict(artifact, incomplete, "ejemplo-sin-datos"))
    return examples


if __name__ == "__main__":
    print(json.dumps(main(Path(__file__).parent / "salidas"), ensure_ascii=False, indent=2))
