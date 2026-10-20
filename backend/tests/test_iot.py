import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.data.models.iot import SensorReading

BATCH = "/api/v1/iot/measurements/batch"


def sensor_type_id(admin_client, code):
    return next(t["id"] for t in admin_client.get("/api/v1/sensor-types").json() if t["code"] == code)


@pytest.fixture
def station(admin_client):
    """Crea atrapanieblas, tanque, dispositivo y sensores; devuelve datos y API key."""
    fog = admin_client.post("/api/v1/fog-collectors", json={"code": "AN-01", "name": "Atrapanieblas 1"}).json()
    tank = admin_client.post("/api/v1/tanks", json={"code": "TQ-01", "name": "Tanque 1"}).json()
    created = admin_client.post(
        "/api/v1/devices", json={"code": "esp32-01", "name": "Estación 1", "fog_collector_id": fog["id"]}
    ).json()
    device = created["device"]
    sensors = {}
    for code, type_code, extra in [
        ("temp", "temperatura", {}),
        ("hum", "humedad_relativa", {}),
        ("vol", "volumen_captado", {}),
        ("nivel", "nivel_almacenamiento", {"tank_id": tank["id"]}),
    ]:
        response = admin_client.post(
            "/api/v1/sensors",
            json={
                "device_id": device["id"],
                "sensor_type_id": sensor_type_id(admin_client, type_code),
                "code": code,
                **extra,
            },
        )
        assert response.status_code == 201, response.text
        sensors[code] = response.json()
    return {"device": device, "key": created["api_key"], "sensors": sensors, "fog": fog}


def headers(station):
    return {"X-Device-Id": station["device"]["code"], "X-Device-Key": station["key"]}


def reading(sensor_code, value, unit, measured_at=None):
    return {
        "message_id": str(uuid.uuid4()),
        "sensor_code": sensor_code,
        "measured_at": (measured_at or datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        "value": value,
        "unit": unit,
    }


def batch(*readings):
    return {"batch_id": str(uuid.uuid4()), "firmware_version": "0.1.0", "readings": list(readings)}


def test_device_key_is_shown_once_and_required(client, station):
    assert station["key"].startswith("dk_")
    assert client.post(BATCH, json=batch(reading("temp", 10, "C"))).status_code == 401
    bad = {"X-Device-Id": "esp32-01", "X-Device-Key": "dk_falsa"}
    assert client.post(BATCH, json=batch(reading("temp", 10, "C")), headers=bad).status_code == 401


def test_valid_batch_is_stored(client, station, db):
    payload = batch(reading("temp", 12.5, "C"), reading("hum", 95, "%"), reading("vol", 1.2, "L"))
    response = client.post(BATCH, json=payload, headers=headers(station))
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["accepted"], body["invalid"], body["rejected"], body["duplicates"]) == (3, 0, 0, 0)
    rows = db.scalars(select(SensorReading)).all()
    assert {r.quality for r in rows} == {"valida"}
    assert all(r.received_at is not None for r in rows)


def test_unmeasured_variable_is_null_not_zero(client, station, db):
    response = client.post(BATCH, json=batch(reading("hum", None, "%")), headers=headers(station))
    assert response.json()["results"][0]["quality"] == "sin_dato"
    row = db.scalars(select(SensorReading)).one()
    assert row.value is None


def test_invalid_values_are_never_stored_as_valid(client, station, db):
    payload = batch(
        reading("hum", 140, "%"),  # fuera de rango
        reading("temp", 20, "F"),  # unidad incorrecta
        reading("vol", -3, "L"),  # volumen negativo
    )
    body = client.post(BATCH, json=payload, headers=headers(station)).json()
    assert body["invalid"] == 3
    qualities = {r.quality for r in db.scalars(select(SensorReading)).all()}
    assert qualities == {"fuera_de_rango", "unidad_invalida"}


def test_future_and_unknown_sensor_readings_are_rejected(client, station, db):
    future = datetime.now(UTC) + timedelta(hours=2)
    payload = batch(reading("temp", 10, "C", measured_at=future), reading("viento", 3, "m/s"))
    body = client.post(BATCH, json=payload, headers=headers(station)).json()
    assert body["rejected"] == 2
    assert db.scalars(select(SensorReading)).all() == []


def test_naive_datetime_is_rejected_by_schema(client, station):
    item = reading("temp", 10, "C")
    item["measured_at"] = "2025-01-01T10:00:00"
    assert client.post(BATCH, json=batch(item), headers=headers(station)).status_code == 422


def test_duplicates_are_prevented(client, station, db):
    first = reading("temp", 10, "C")
    payload = batch(first)
    assert client.post(BATCH, json=payload, headers=headers(station)).json()["status"] == "procesado"
    # Reenvío del mismo lote (p. ej. el ESP32 no recibió la respuesta).
    again = client.post(BATCH, json=payload, headers=headers(station)).json()
    assert again["status"] == "duplicado"
    # Lote nuevo que repite una lectura ya almacenada.
    mixed = client.post(BATCH, json=batch(first, reading("temp", 11, "C")), headers=headers(station)).json()
    assert (mixed["accepted"], mixed["duplicates"]) == (1, 1)
    assert len(db.scalars(select(SensorReading)).all()) == 2


def test_inactive_device_cannot_send(client, admin_client, station):
    admin_client.delete(f"/api/v1/devices/{station['device']['id']}")
    response = client.post(BATCH, json=batch(reading("temp", 10, "C")), headers=headers(station))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "dispositivo_inactivo"


def test_rotated_key_invalidates_previous(client, admin_client, station):
    new_key = admin_client.post(f"/api/v1/devices/{station['device']['id']}/credentials").json()["api_key"]
    assert client.post(BATCH, json=batch(reading("temp", 10, "C")), headers=headers(station)).status_code == 401
    new_headers = {"X-Device-Id": "esp32-01", "X-Device-Key": new_key}
    assert client.post(BATCH, json=batch(reading("temp", 10, "C")), headers=new_headers).status_code == 200


def test_volume_sensor_requires_fog_collector(admin_client):
    device = admin_client.post("/api/v1/devices", json={"code": "esp32-02", "name": "Sin atrapanieblas"}).json()
    response = admin_client.post(
        "/api/v1/sensors",
        json={
            "device_id": device["device"]["id"],
            "sensor_type_id": sensor_type_id(admin_client, "volumen_captado"),
            "code": "vol",
        },
    )
    assert response.json()["error"]["code"] == "atrapanieblas_requerido"


def test_dashboard_summary_and_staleness(client, admin_client, station):
    summary = admin_client.get("/api/v1/dashboard/summary").json()
    assert summary["devices"][0]["is_stale"] is True
    assert summary["has_stale_data"] is True

    old = datetime.now(UTC) - timedelta(hours=3)
    client.post(
        BATCH,
        json=batch(reading("temp", 9, "C"), reading("vol", 2.5, "L"), reading("hum", 80, "%", measured_at=old)),
        headers=headers(station),
    )
    summary = admin_client.get("/api/v1/dashboard/summary").json()
    assert summary["devices"][0]["is_stale"] is False
    assert summary["last_communication_at"] is not None
    latest = {v["sensor_code"]: v for v in summary["latest"]}
    assert latest["temp"]["is_stale"] is False
    assert latest["hum"]["is_stale"] is True
    assert summary["volume"]["last_7_days_liters"] == 2.5


def test_volume_series_sums_incremental_values(client, admin_client, station):
    base = datetime.now(UTC) - timedelta(days=2)
    payload = batch(
        reading("vol", 1.0, "L", measured_at=base),
        reading("vol", 2.0, "L", measured_at=base + timedelta(minutes=10)),
        reading("vol", 999, "L", measured_at=base + timedelta(minutes=20)),
        reading("vol", 5000, "L", measured_at=base + timedelta(minutes=30)),  # fuera de rango: excluida
        reading("temp", 10, "C", measured_at=base),
        reading("temp", 20, "C", measured_at=base + timedelta(minutes=5)),
    )
    client.post(BATCH, json=payload, headers=headers(station))

    volume = admin_client.get(
        "/api/v1/dashboard/series",
        params={"sensor_type": "volumen_captado", "bucket": "month", "fog_collector_id": station["fog"]["id"]},
    ).json()
    assert volume["aggregation"] == "incremental"
    assert sum(p["value"] for p in volume["points"]) == pytest.approx(1002.0)

    temp = admin_client.get("/api/v1/dashboard/series", params={"sensor_type": "temperatura", "bucket": "month"}).json()
    assert temp["aggregation"] == "instantaneo"
    assert temp["points"][0]["value"] == pytest.approx(15.0)


def test_measurements_history_filters(client, admin_client, station):
    client.post(BATCH, json=batch(reading("temp", 10, "C"), reading("hum", 140, "%")), headers=headers(station))
    all_rows = admin_client.get("/api/v1/measurements").json()
    assert all_rows["total"] == 2
    valid = admin_client.get("/api/v1/measurements", params={"quality": "valida"}).json()
    assert valid["total"] == 1
    by_type = admin_client.get("/api/v1/measurements", params={"sensor_type": "humedad_relativa"}).json()
    assert by_type["items"][0]["quality"] == "fuera_de_rango"


def test_fog_collector_overview_integrates_stations(client, admin_client, station):
    from app.business.services.fog_collector_service import fog_collector_status

    client.post(BATCH, json=batch(reading("vol", 2.5, "L")), headers=headers(station))
    overview = admin_client.get("/api/v1/fog-collectors/overview").json()
    fc = next(f for f in overview if f["stations"])
    assert fc["status"] == "operativo"
    assert fc["stations"][0]["is_stale"] is False
    assert fc["volume_last_7_days"] == 2.5
    updated = admin_client.put(f"/api/v1/fog-collectors/{fc['id']}", json={"orientation": "NE"})
    assert updated.json()["orientation"] == "NE"

    stale = [{"status": "activo", "is_stale": True}]
    assert fog_collector_status(is_active=True, stations=stale, incidents_in_attention=0) == "sin_datos_recientes"
    assert fog_collector_status(is_active=True, stations=stale, incidents_in_attention=1) == "mantenimiento"
    assert fog_collector_status(is_active=True, stations=[], incidents_in_attention=0) == "sin_estacion"
    assert fog_collector_status(is_active=False, stations=stale, incidents_in_attention=0) == "inactivo"
