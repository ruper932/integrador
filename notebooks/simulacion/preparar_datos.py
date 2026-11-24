"""Paso 2 — Preparación del conjunto diario de entrenamiento.

Horizonte SUPUESTO (pendiente de confirmación): predecir el volumen total captado el día D+1
con la información disponible al cierre del día D. Ninguna variable usa datos posteriores a D.

Las mismas transformaciones servirán para los datos reales exportados desde `sensor_readings`
(lecturas con calidad `valida`), agregados por día en hora de Bolivia.
"""

import sys
from pathlib import Path

import pandas as pd

# Las transformaciones viven en el backend para que el entrenamiento y la API usen el mismo código.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.business.ml.features import FEATURES, MIN_HOURLY_COVERAGE, TARGET, build_daily  # noqa: E402

__all__ = ["FEATURES", "MIN_HOURLY_COVERAGE", "TARGET", "build_daily"]


def main(hourly_path: Path, output_dir: Path) -> Path:
    daily = build_daily(pd.read_csv(hourly_path))
    path = output_dir / "dataset_diario.csv"
    daily.to_csv(path, index_label="fecha")
    return path


if __name__ == "__main__":
    out = Path(__file__).parent / "salidas"
    print(main(out / "lecturas_horarias_sinteticas.csv", out))
