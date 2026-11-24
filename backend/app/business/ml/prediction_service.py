"""Estimación PROVISIONAL del volumen con el único modelo de ML y datos en vivo de las estaciones.

Marca interna: el artefacto disponible es el de la simulación (`sim-*`), entrenado con datos
sintéticos. Sirve para ver el flujo funcionando con lecturas reales, no para planificar: sus cifras no
están validadas. Las estimaciones se calculan al consultar y no se guardan; las tablas
`ml_models`/`predictions` y la comparación real vs. estimado quedan para el modelo de producción.

Para cada estación conectada se arma el día base D (ayer, completo, hora de Bolivia) con el mismo
código de preparación del entrenamiento y se estima el volumen de hoy (D+1).
"""

import warnings
from datetime import datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import joblib
import pandas as pd
from sklearn.exceptions import InconsistentVersionWarning
from sqlalchemy.orm import Session

from app.business.ml.features import build_daily
from app.business.ml.inference import predict
from app.business.services.measurement_service import MeasurementService
from app.core.clock import utcnow
from app.core.config import get_settings
from app.data.models.iot import Device
from app.data.repositories.iot import DeviceRepository

PROVISIONAL = True
TRAINING_MESH_AREA_M2 = 40.0  # área de malla de los datos sintéticos (notebooks/simulacion/generar_datos.py)
HISTORY_DAYS = 7  # días previos al día base: volumen del día anterior y media de 7 días
# Mismos códigos que los tipos de sensor del sistema y que las columnas usadas al entrenar.
VARIABLES = (
    "temperatura",
    "humedad_relativa",
    "presion_atmosferica",
    "velocidad_viento",
    "niebla",
    "volumen_captado",
)
VOLUME_FEATURES = ("volumen_dia", "volumen_dia_anterior", "volumen_media_7d")


@lru_cache(maxsize=2)
def _load(path: str, modified: float) -> dict[str, Any]:
    # El artefacto viene de la ubicación controlada (montada de solo lectura); joblib ejecuta pickle.
    with warnings.catch_warnings():
        warnings.simplefilter("error", InconsistentVersionWarning)
        return joblib.load(path)


def load_artifact(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Artefacto cargado (se relee si cambia el archivo) o el motivo por el que no está disponible."""
    if not path.is_file():
        return None, f"No se encontró el artefacto del modelo ({path.name}) en la carpeta de artefactos."
    try:
        return _load(str(path), path.stat().st_mtime), None
    except InconsistentVersionWarning:
        return None, "El artefacto fue entrenado con otra versión de scikit-learn; vuelva a entrenarlo."
    except Exception:  # noqa: BLE001 - un artefacto dañado no debe tumbar la API
        return None, "El artefacto del modelo no se pudo leer."


class ProvisionalPredictionService:
    def __init__(self, session: Session) -> None:
        self.settings = get_settings()
        self.tz = ZoneInfo(self.settings.local_timezone)
        self.devices = DeviceRepository(session)
        self.measurements = MeasurementService(session)

    def estimate(self) -> dict[str, Any]:
        now = utcnow()
        today = now.astimezone(self.tz).date()
        base_day = today - timedelta(days=1)
        artifact, reason = load_artifact(self.settings.ml_artifact_path)
        stale = timedelta(minutes=self.settings.device_stale_minutes)
        connected = [
            d
            for d in self.devices.list(limit=1000, order_by=Device.code)
            if d.status == "activo" and d.last_seen_at and now - d.last_seen_at <= stale
        ]
        metadata = artifact["metadata"] if artifact else {}
        return {
            "provisional": PROVISIONAL,
            "modelo_disponible": artifact is not None,
            "motivo": reason,
            "version_modelo": metadata.get("version_modelo"),
            "horizonte": metadata.get("horizonte_supuesto"),
            "metricas_simulacion": metadata.get("metricas_prueba"),
            "generado_en": now,
            "dia_base": base_day,
            "fecha_predicha": today,
            "estaciones": [self._station(d, artifact, base_day, now) for d in connected] if artifact else [],
        }

    def _hourly(self, device: Device, start: datetime, end: datetime) -> pd.DataFrame:
        """Lecturas válidas por hora (vacío donde no hubo lectura, nunca 0)."""
        index = pd.date_range(
            pd.Timestamp(start).tz_convert("UTC"), pd.Timestamp(end).tz_convert("UTC"), freq="h", inclusive="left"
        )
        hourly = pd.DataFrame(index=index, columns=list(VARIABLES), dtype=float)
        for code in VARIABLES:
            series = self.measurements.series(
                sensor_type_code=code, bucket="hour", date_from=start, date_to=end, device_id=device.id
            )
            for point in series.points:
                hourly.loc[pd.Timestamp(point.bucket).tz_convert("UTC"), code] = point.value
        return hourly.rename_axis("measured_at").reset_index()

    def _station(self, device: Device, artifact: dict[str, Any], base_day: Any, now: datetime) -> dict[str, Any]:
        start = datetime.combine(base_day - timedelta(days=HISTORY_DAYS), time(), self.tz)
        hourly = self._hourly(device, start, now)
        daily = build_daily(hourly)
        row = daily.loc[pd.Timestamp(base_day)] if pd.Timestamp(base_day) in daily.index else pd.Series(dtype=float)
        variables = {f: (None if pd.isna(row.get(f)) else round(float(row[f]), 3)) for f in artifact["features"]}

        # El modelo aprendió litros de una malla de 40 m²: el volumen se lleva a esa escala y se devuelve.
        collector = device.fog_collector
        area = float(collector.mesh_area_m2) if collector and collector.mesh_area_m2 else None
        factor = TRAINING_MESH_AREA_M2 / area if area else 1.0
        scaled = row.copy()
        for feature in VOLUME_FEATURES:
            if feature in scaled:
                scaled[feature] = scaled[feature] * factor
        result = predict(artifact, scaled, (base_day + timedelta(days=1)).isoformat())
        estimate = result["resultado_litros"]

        local_day = pd.to_datetime(hourly["measured_at"]).dt.tz_convert(self.tz).dt.date
        today_volume = hourly.loc[local_day == base_day + timedelta(days=1), "volumen_captado"].sum(min_count=1)
        return {
            "device_id": device.id,
            "device_code": device.code,
            "device_name": device.name,
            "fog_collector": collector.name if collector else None,
            "mesh_area_m2": area,
            "last_seen_at": device.last_seen_at,
            "estado": result["estado"],
            "resultado_litros": round(estimate / factor, 2) if estimate is not None else None,
            "referencia_media_7d_litros": variables.get("volumen_media_7d"),
            "captado_hoy_litros": None if pd.isna(today_volume) else round(float(today_volume), 2),
            "variables": variables,
            "faltantes": [f for f, v in variables.items() if v is None],  # también si se estimó sin ellas
        }
