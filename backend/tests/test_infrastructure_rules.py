"""Reglas entre formularios de infraestructura: referencias activas y datos que dependen de otros."""

from datetime import date, timedelta

import pytest

API = "/api/v1"


@pytest.fixture
def two_collectors(admin_client):
    loc = admin_client.post(f"{API}/locations", json={"name": "Ladera"}).json()
    a = admin_client.post(
        f"{API}/fog-collectors", json={"code": "AN-A", "name": "Norte", "location_id": loc["id"]}
    ).json()
    b = admin_client.post(f"{API}/fog-collectors", json={"code": "AN-B", "name": "Sur"}).json()
    tank_b = admin_client.post(
        f"{API}/tanks", json={"code": "TQ-B", "name": "Tanque B", "fog_collector_id": b["id"]}
    ).json()
    device = admin_client.post(
        f"{API}/devices", json={"code": "esp32-a", "name": "Estación A", "fog_collector_id": a["id"]}
    ).json()["device"]
    types = {t["code"]: t["id"] for t in admin_client.get(f"{API}/sensor-types").json()}
    return {"loc": loc, "a": a, "b": b, "tank_b": tank_b, "device": device, "types": types}


def sensor(client, data, **payload):
    return client.post(f"{API}/sensors", json={"device_id": data["device"]["id"], "code": "s1"} | payload)


def test_sensor_must_use_the_fog_collector_of_its_device(admin_client, two_collectors):
    d = two_collectors
    other = sensor(admin_client, d, sensor_type_id=d["types"]["volumen_captado"], fog_collector_id=d["b"]["id"])
    assert other.status_code == 422
    assert other.json()["error"]["code"] == "atrapanieblas_distinto"
    # Sin indicarlo, el sensor toma el atrapanieblas del dispositivo.
    ok = sensor(admin_client, d, sensor_type_id=d["types"]["volumen_captado"])
    assert ok.status_code == 201
    assert ok.json()["fog_collector_id"] == d["a"]["id"]


def test_tank_must_belong_to_the_sensor_fog_collector(admin_client, two_collectors):
    d = two_collectors
    response = sensor(admin_client, d, sensor_type_id=d["types"]["nivel_almacenamiento"], tank_id=d["tank_b"]["id"])
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "tanque_de_otro_atrapanieblas"


def test_inactive_references_are_rejected(admin_client, two_collectors):
    d = two_collectors
    admin_client.delete(f"{API}/fog-collectors/{d['b']['id']}")
    device = admin_client.post(
        f"{API}/devices", json={"code": "esp32-b", "name": "Estación B", "fog_collector_id": d["b"]["id"]}
    )
    assert device.status_code == 422
    tank = admin_client.post(
        f"{API}/tanks", json={"code": "TQ-X", "name": "Tanque X", "fog_collector_id": d["b"]["id"]}
    )
    assert tank.json()["error"]["code"] == "referencia_invalida"
    admin_client.delete(f"{API}/locations/{d['loc']['id']}")
    fc = admin_client.post(
        f"{API}/fog-collectors", json={"code": "AN-C", "name": "Centro", "location_id": d["loc"]["id"]}
    )
    assert fc.json()["error"]["code"] == "referencia_invalida"
    # Una referencia que no cambia se conserva aunque se haya desactivado.
    keep = admin_client.put(f"{API}/fog-collectors/{d['a']['id']}", json={"location_id": d["loc"]["id"], "name": "A2"})
    assert keep.status_code == 200


def test_location_coordinates_go_together(admin_client):
    half = admin_client.post(f"{API}/locations", json={"name": "Media", "latitude": "-15.4"})
    assert half.status_code == 422
    assert half.json()["error"]["code"] == "coordenadas_incompletas"
    full = admin_client.post(f"{API}/locations", json={"name": "Completa", "latitude": "-15.4", "longitude": "-68.9"})
    assert full.status_code == 201
    cleared = admin_client.put(f"{API}/locations/{full.json()['id']}", json={"longitude": None})
    assert cleared.status_code == 422


def test_installation_date_cannot_be_in_the_future(admin_client):
    tomorrow = (date.today() + timedelta(days=2)).isoformat()
    response = admin_client.post(
        f"{API}/fog-collectors", json={"code": "AN-F", "name": "Futuro", "installed_on": tomorrow}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "fecha_futura"
