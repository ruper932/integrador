# Notebooks y scripts de machine learning

Entorno separado de la API (el entrenamiento no se ejecuta dentro del backend).

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## `simulacion/` — simulación con datos sintéticos

Prueba el flujo del único modelo de predicción de volumen antes de contar con datos reales.
**No es el modelo de producción** (pendiente). Resultados y supuestos: [../docs/simulacion_ml.md](../docs/simulacion_ml.md).

| Paso | Script |
|---|---|
| 1. Datos horarios sintéticos | `generar_datos.py` |
| 2. Conjunto diario (sin datos futuros) | `preparar_datos.py` |
| 3. Entrenamiento y evaluación temporal | `entrenar_evaluar.py` |
| 4. Inferencia de ejemplo | `inferir.py` |
| Todo | `ejecutar.py` |
