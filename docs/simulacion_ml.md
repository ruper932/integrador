# Simulación del modelo de predicción de volumen

> **Esto es una simulación con datos sintéticos.** El modelo de producción sigue **pendiente**:
> falta confirmar el horizonte de predicción y las variables reales, y contar con datos de la estación.
> Las métricas de este documento **no** indican el desempeño que tendrá el sistema real.

## Objetivo

Probar de punta a punta el flujo que exige `AGENTS.md` para el único modelo de ML, antes de
tener datos reales: preparación de datos, entrenamiento, validación temporal, métricas, artefacto
versionado, inferencia que informa cuando no hay datos suficientes, y comparación real vs. estimado.

No se modificó la API ni la base de datos. Todo vive en `notebooks/simulacion/`, en un entorno
de Python separado del backend, porque el entrenamiento debe estar separado de la API.

## Supuestos

| Aspecto | Supuesto usado en la simulación |
|---|---|
| Horizonte | Volumen total del día D+1, con los datos disponibles al cierre del día D |
| Datos | 2 años de lecturas horarias sintéticas, 40 m² de malla, 2 % de lecturas faltantes (`null`) |
| Clima sintético | Estación húmeda con más niebla (dic–mar) y estación seca (may–ago); episodios de niebla nocturnos; régimen húmedo que persiste varios días y baja la presión |
| Escala | Media de unos 30 L/día (≈ 0,7 L/m²/día); unos 70 L/día en febrero y 4 L/día en julio |
| Variables de entrada | Volumen del día, del día anterior y media de 7 días; humedad (media, máxima, horas ≥ 95 %); temperatura (media, rango); viento medio; presión (media, cambio); niebla (media, horas ≥ 40 %, últimas 6 h); estacionalidad (seno/coseno del día del año) |
| Modelo | `HistGradientBoostingRegressor` de scikit-learn (admite valores faltantes sin rellenarlos con 0) |

Ninguna variable de entrada usa información posterior al día D. El único dato "futuro" es el objetivo.

## Validación

- Partición temporal: entrenamiento del 2024-01-01 al 2025-05-24 (510 días) y prueba del
  2025-05-25 al 2025-12-29 (219 días, nunca vistos durante el entrenamiento).
- Los hiperparámetros se eligieron con `TimeSeriesSplit` (5 cortes) dentro del periodo de
  entrenamiento. Resultado: `max_depth=3`, `learning_rate=0.03`, `max_iter=200`, `min_samples_leaf=20`.
- Se compara contra dos referencias simples, que no son modelos de producción: persistencia
  (mañana = hoy) y media móvil de 7 días.

## Resultados (periodo de prueba)

| | MAE (L/día) | RMSE (L/día) | R² |
|---|---:|---:|---:|
| Modelo | 14,7 | 21,3 | 0,38 |
| Referencia: persistencia | 17,0 | 27,4 | −0,02 |
| Referencia: media de 7 días | **14,1** | **20,9** | **0,41** |

Volumen medio diario real en el periodo de prueba: 17,9 L.

Totales mensuales (real vs. estimado, en litros):

| Mes | Real | Estimado | MAE diario |
|---|---:|---:|---:|
| 2025-06 | 212 | 309 | 10,5 |
| 2025-07 | 104 | 249 | 6,9 |
| 2025-08 | 151 | 203 | 7,9 |
| 2025-09 | 207 | 221 | 10,3 |
| 2025-10 | 332 | 439 | 12,6 |
| 2025-11 | 1120 | 930 | 22,7 |
| 2025-12 | 1678 | 1514 | 34,0 |

## Lectura de los resultados

1. **El flujo funciona** de punta a punta y respeta las reglas: validación temporal, sin datos
   futuros, artefacto versionado con metadatos, estado `datos_insuficientes` cuando falta el
   volumen del día o la humedad, o más del 30 % de las variables.
2. **El modelo no superó a la media móvil de 7 días** en estos datos sintéticos. Sí supera
   claramente a la persistencia. No se ajustó el generador para que el modelo "ganara".
3. **Sesgo estacional:** sobrestima en la época seca y subestima en la húmeda. El periodo de
   prueba (mayo–diciembre) incluye una transición estacional que el entrenamiento solo vio una vez.

## Implicaciones para el modelo real

- Se necesita **al menos un año completo** de datos reales (idealmente dos) para cubrir ambas
  estaciones antes de evaluar con seriedad.
- La evaluación con datos reales debe incluir **siempre** las referencias de persistencia y de
  media de 7 días. Si el modelo no las supera, se debe informar así y no prometer precisión.
- Conviene revisar si el horizonte D+1 es el útil para planificar el riego, o si conviene otro
  (por ejemplo, el volumen acumulado de la semana).
- Pendiente de decidir: horizonte, variables disponibles según los sensores instalados, frecuencia
  de reentrenamiento (controlado y documentado) y umbral mínimo de datos.

## Código compartido con la API

La preparación de variables (`build_daily`) y las reglas de inferencia (`predict`) están en
`backend/app/business/ml/` y la simulación las importa. Así el entrenamiento y el módulo provisional
«Estimación de volumen» calculan las variables con el mismo código. Para publicar un artefacto
entrenado, copiarlo a `backend/artifacts/`.

## Cómo reproducir

```bash
cd notebooks
python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python simulacion/ejecutar.py
```

Salidas en `notebooks/simulacion/salidas/` (no versionadas, se regeneran con semilla fija):
`lecturas_horarias_sinteticas.csv`, `dataset_diario.csv`, `metricas.json`,
`comparacion_real_vs_estimado.csv`, `modelo_sim-0.1.0.joblib`.
