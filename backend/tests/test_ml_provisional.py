"""Módulo provisional: estimación con el modelo de ML y datos en vivo de las estaciones conectadas."""

from datetime import UTC, datetime, timedelta

import joblib
import pandas as pd
import pytest
from sklearn.dummy import DummyRegressor

from app.business.ml.features import FEATURES
from app.core.config import get_settings
from tests.test_iot import BATCH, batch, headers, reading, sensor_type_id, station  # noqa: F401

URL = "/api/v1/ml/provisional"


@pytest.fixture
def artifact(tmp_path, monkeypatch):
    """Modelo de prueba que siempre estima 20 L (para una malla de 40 m², como el entrenamiento)."""
    model = DummyRegressor(strategy="constant", constant=20.0).fit(
        pd.DataFrame([[0.0] * len(FEATURES)], columns=FEATURES), [20.0]
    )
    path = tmp_path / "modelo_prueba.joblib"
    joblib.dump(
        {"model": model, "features": FEATURES, "metadata": {"version_modelo": "sim-test", "metricas_prueba": {}}}, path
    )
    monkeypatch.setattr(get_settings(), "ml_artifact_path", path)
    return path


def test_any_role_sees_the_module_and_no_station_means_no_data(make_client, factory, artifact):
    for role in ("docente", "mantenimiento", "director"):
        response = factory.client_for(make_client(), f"ml-{role}", [role]).get(URL)
        assert response.status_code == 200, response.text
    body = response.json()
    assert body["provisional"] is True
    assert body["modelo_disponible"] is True
    assert body["estaciones"] == []  # la interfaz muestra «Sin datos disponibles»
    assert make_client().get(URL).status_code == 401


def test_connected_station_gets_an_estimate_scaled_to_its_mesh(admin_client, client, station, artifact):  # noqa: F811
    admin_client.put(f"/api/v1/fog-collectors/{station['fog']['id']}", json={"mesh_area_m2": "20"})
    admin_client.post(
        "/api/v1/sensors",
        json={
            "device_id": station["device"]["id"],
            "sensor_type_id": sensor_type_id(admin_client, "presion_atmosferica"),
            "code": "pres",
        },
    )
    # Estación como la de DHT11 + BME280: temperatura, humedad, presión y volumen; sin viento ni niebla.
    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    readings = []
    for hour in range(1, 9 * 24):
        at = now - timedelta(hours=hour)
        readings += [
            reading("temp", 10, "C", at),
            reading("hum", 92, "%", at),
            reading("pres", 690, "hPa", at),
            reading("vol", 1.0, "L", at),
        ]
    for i in range(0, len(readings), 500):  # máximo de lecturas por lote
        assert client.post(BATCH, json=batch(*readings[i : i + 500]), headers=headers(station)).status_code == 200

    estimate = admin_client.get(URL).json()["estaciones"][0]
    assert estimate["estado"] == "generada"
    assert estimate["resultado_litros"] == 10.0  # 20 L para 40 m² → 10 L para la malla de 20 m²
    assert estimate["referencia_media_7d_litros"] == 24.0
    assert estimate["variables"]["horas_niebla_40"] is None  # sin sensor de niebla: vacío, no 0
    assert set(estimate["faltantes"]) == {"viento_medio", "niebla_media", "horas_niebla_40", "niebla_ultimas_6h"}


def test_station_without_history_reports_insufficient_data(admin_client, client, station, artifact):  # noqa: F811
    client.post(BATCH, json=batch(reading("hum", 80, "%")), headers=headers(station))
    estimate = admin_client.get(URL).json()["estaciones"][0]
    assert estimate["estado"] == "datos_insuficientes"
    assert estimate["resultado_litros"] is None
    assert "volumen_dia" in estimate["faltantes"]


def test_missing_artifact_is_reported(admin_client, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "ml_artifact_path", tmp_path / "no_existe.joblib")
    body = admin_client.get(URL).json()
    assert body["modelo_disponible"] is False
    assert "No se encontró" in body["motivo"]
    assert body["estaciones"] == []
