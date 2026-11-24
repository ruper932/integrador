"""Intervalo de muestreo por estación y panel de monitoreo en vivo."""

from datetime import UTC, datetime, timedelta

from tests.test_iot import BATCH, batch, headers, reading, station  # noqa: F401 (fixture)

LIVE = "/api/v1/dashboard/live"


def test_batch_response_tells_the_station_its_sample_interval(client, admin_client, station):  # noqa: F811
    # Arrange: estación nueva, intervalo por defecto
    device_id = station["device"]["id"]
    assert station["device"]["sample_interval_s"] == 60
    # Act
    first = client.post(BATCH, json=batch(reading("temp", 11, "C")), headers=headers(station))
    changed = admin_client.put(f"/api/v1/devices/{device_id}", json={"sample_interval_s": 5})
    second = client.post(BATCH, json=batch(reading("temp", 11.5, "C")), headers=headers(station))
    # Assert: la estación recibe el nuevo intervalo en el siguiente lote
    assert first.json()["sample_interval_s"] == 60
    assert changed.status_code == 200, changed.text
    assert changed.json()["sample_interval_s"] == 5
    assert second.json()["sample_interval_s"] == 5
    audit = admin_client.get("/api/v1/admin/audit-logs", params={"action": "dispositivo.actualizar"}).json()
    assert any(item["details"].get("sample_interval_s") == "5" for item in audit["items"])


def test_only_allowed_intervals_and_only_managers_can_change_it(client, admin_client, factory, station):  # noqa: F811
    device_id = station["device"]["id"]
    docente = factory.client_for(client, "docente1", ["docente"])

    assert admin_client.put(f"/api/v1/devices/{device_id}", json={"sample_interval_s": 10}).status_code == 422
    assert docente.put(f"/api/v1/devices/{device_id}", json={"sample_interval_s": 5}).status_code == 403
    # Un null explícito no borra el intervalo
    keep = admin_client.put(f"/api/v1/devices/{device_id}", json={"sample_interval_s": None})
    assert keep.status_code == 200 and keep.json()["sample_interval_s"] == 60


def test_live_window_groups_valid_readings_by_variable(client, admin_client, station):  # noqa: F811
    # Arrange: dos lecturas dentro de la ventana, una antigua y una inválida
    now = datetime.now(UTC)
    payload = batch(
        reading("temp", 10.0, "C", now - timedelta(minutes=2)),
        reading("temp", 14.0, "C", now - timedelta(minutes=1)),
        reading("temp", 30.0, "C", now - timedelta(hours=3)),
        reading("hum", 140.0, "%", now - timedelta(minutes=1)),  # fuera de rango: no es válida
    )
    assert client.post(BATCH, json=payload, headers=headers(station)).status_code == 200
    # Act
    response = admin_client.get(LIVE, params={"device_id": station["device"]["id"], "minutes": 15})
    # Assert
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["device"]["sample_interval_s"] == 60 and body["window_minutes"] == 15
    by_code = {v["sensor_type"]["code"]: v for v in body["variables"]}
    temp = by_code["temperatura"]
    assert [p["v"] for p in temp["points"]] == [10.0, 14.0]
    assert (temp["minimum"], temp["maximum"], temp["average"], temp["latest_value"]) == (10.0, 14.0, 12.0, 14.0)
    hum = by_code["humedad_relativa"]
    assert hum["points"] == [] and hum["latest_value"] is None  # la inválida no se muestra


def test_live_window_limits(admin_client, station):  # noqa: F811
    device_id = station["device"]["id"]
    assert admin_client.get(LIVE, params={"device_id": device_id, "minutes": 0}).status_code == 422
    assert admin_client.get(LIVE, params={"device_id": device_id, "minutes": 361}).status_code == 422
    assert admin_client.get(LIVE, params={"device_id": 999_999}).status_code == 404
