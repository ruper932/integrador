"""Paso 3 — Entrenamiento y evaluación del ÚNICO modelo (simulación con datos sintéticos).

- Modelo: HistGradientBoostingRegressor (admite valores faltantes sin imputar con ceros).
- Validación temporal: los hiperparámetros se eligen con TimeSeriesSplit dentro del periodo de
  entrenamiento; la evaluación final usa el último 30 % del periodo, nunca visto.
- Referencias (no son modelos de producción): persistencia (mañana = hoy) y media móvil de 7 días.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from preparar_datos import FEATURES, TARGET
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit

MODEL_VERSION = "sim-0.1.0"
TEST_FRACTION = 0.30
PARAM_GRID = {
    "max_depth": [3, 5],
    "learning_rate": [0.03, 0.08],
    "max_iter": [200, 400],
    "min_samples_leaf": [10, 20],
}


def metrics(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "mae_litros": round(float(mean_absolute_error(y_true, y_pred)), 3),
        "rmse_litros": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 3),
        "r2": round(float(r2_score(y_true, y_pred)), 3),
    }


def main(dataset_path: Path, output_dir: Path) -> dict:
    data = pd.read_csv(dataset_path, index_col="fecha", parse_dates=True).sort_index()
    data = data.dropna(subset=[TARGET])  # sin objetivo conocido no hay con qué evaluar
    split = int(len(data) * (1 - TEST_FRACTION))
    train, test = data.iloc[:split], data.iloc[split:]

    search = GridSearchCV(
        HistGradientBoostingRegressor(random_state=0),
        PARAM_GRID,
        cv=TimeSeriesSplit(n_splits=5),
        scoring="neg_mean_absolute_error",
        n_jobs=-1,
    )
    search.fit(train[FEATURES], train[TARGET])
    model = search.best_estimator_
    predictions = model.predict(test[FEATURES])

    persistence = test["volumen_dia"].fillna(train[TARGET].mean())
    rolling = test["volumen_media_7d"].fillna(train[TARGET].mean())

    report = {
        "advertencia": "SIMULACIÓN con datos sintéticos. Las métricas no representan el desempeño real.",
        "version_modelo": MODEL_VERSION,
        "horizonte_supuesto": "Volumen total del día siguiente (D+1) con datos disponibles al cierre del día D",
        "entrenado_en": datetime.now(UTC).isoformat(timespec="seconds"),
        "periodo_entrenamiento": [str(train.index.min().date()), str(train.index.max().date())],
        "periodo_prueba": [str(test.index.min().date()), str(test.index.max().date())],
        "dias_entrenamiento": len(train),
        "dias_prueba": len(test),
        "variables": FEATURES,
        "hiperparametros": search.best_params_,
        "mae_validacion_cruzada_temporal": round(-float(search.best_score_), 3),
        "metricas_prueba": {
            "modelo": metrics(test[TARGET], predictions),
            "referencia_persistencia": metrics(test[TARGET], persistence),
            "referencia_media_7d": metrics(test[TARGET], rolling),
        },
        "volumen_medio_diario_prueba_litros": round(float(test[TARGET].mean()), 3),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    # Artefacto versionado con sus metadatos; queda fuera de backend/artifacts porque no es de producción.
    joblib.dump(
        {"model": model, "features": FEATURES, "metadata": report}, output_dir / f"modelo_{MODEL_VERSION}.joblib"
    )
    (output_dir / "metricas.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(
        {
            "volumen_real": test[TARGET].round(3),
            "volumen_estimado": predictions.round(3),
            "error": (predictions - test[TARGET]).round(3),
        },
        index=test.index.shift(1, freq="D").rename("fecha_predicha"),
    ).to_csv(output_dir / "comparacion_real_vs_estimado.csv")
    return report


if __name__ == "__main__":
    out = Path(__file__).parent / "salidas"
    print(json.dumps(main(out / "dataset_diario.csv", out), ensure_ascii=False, indent=2))
