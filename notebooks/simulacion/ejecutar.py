"""Ejecuta la simulación completa: datos sintéticos → preparación → entrenamiento/evaluación → inferencia."""

import json
from pathlib import Path

import entrenar_evaluar
import generar_datos
import inferir
import preparar_datos

OUT = Path(__file__).parent / "salidas"

if __name__ == "__main__":
    hourly = generar_datos.main(OUT)
    dataset = preparar_datos.main(hourly, OUT)
    report = entrenar_evaluar.main(dataset, OUT)
    print(json.dumps(report["metricas_prueba"], ensure_ascii=False, indent=2))
    print(json.dumps(inferir.main(OUT), ensure_ascii=False, indent=2))
