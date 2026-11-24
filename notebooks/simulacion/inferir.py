"""Paso 4 — Inferencia de ejemplo con el artefacto de la simulación.

Muestra el comportamiento previsto para el futuro servicio de predicción:
- Informa explícitamente cuando no hay datos suficientes (no inventa una predicción).
- Devuelve fecha, variables usadas, resultado, versión del modelo y estado.
"""

import json
import math
import sys
from pathlib import Path

import joblib
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.business.ml.inference import predict  # noqa: E402


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
