"""Regresiones de la revisión de validaciones por módulo (noviembre 2026)."""

import pytest

from tests.test_incidents import INCIDENTS, finish_payload, report
from tests.test_users_rbac import profile, role_id

pytest_plugins = ["tests.test_incidents"]  # fixtures station y people

NAIVE = "2026-01-01T00:00:00"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/measurements",
        "/api/v1/dashboard/series?sensor_type=temperatura",
        "/api/v1/analysis",
        "/api/v1/reports/export?report=mediciones&format=csv",
        "/api/v1/inventory/reports/movements",
        "/api/v1/maintenance",
        "/api/v1/incidents?scope=all",
        "/api/v1/relocations?scope=all",
        "/api/v1/admin/audit-logs",
    ],
)
def test_date_filters_require_a_timezone(admin_client, path):
    # Antes: 500 en series, análisis y reportes; en el resto, una hora ambigua.
    sep = "&" if "?" in path else "?"
    response = admin_client.get(f"{path}{sep}date_from={NAIVE}")
    assert response.status_code == 422
    assert admin_client.get(f"{path}{sep}date_from={NAIVE}Z").status_code == 200


@pytest.mark.parametrize("names", [{"first_names": "   "}, {"first_names": "--"}, {"paternal_surname": ".."}])
def test_names_must_contain_letters(admin_client, names):
    payload = {"username": "sinletras", "profile": profile(**names), "role_ids": [role_id(admin_client, "docente")]}
    assert admin_client.post("/api/v1/users", json=payload).status_code == 422


def test_item_unit_is_fixed_once_it_has_movements(admin_client, station):
    url = f"/api/v1/inventory/items/{station['item']['id']}"  # creado con stock inicial (un movimiento)
    response = admin_client.put(url, json={"unit": "metro"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unidad_con_movimientos"
    assert admin_client.put(url, json={"unit": "unidad", "name": "Silicona neutra"}).status_code == 200


def test_finishing_without_device_keeps_the_reported_sensor(people, station):
    sensor_id = station["sensor"]["id"]
    created = report(people["docente"], station, sensor_id=sensor_id)
    tecnico = people["tecnico"]
    tecnico.post(f"{INCIDENTS}/{created['id']}/accept")
    tecnico.post(f"{INCIDENTS}/{created['id']}/start")
    response = tecnico.post(f"{INCIDENTS}/{created['id']}/finish", json=finish_payload())
    assert response.status_code == 200, response.text
    assert response.json()["maintenance"]["sensor_id"] == sensor_id


def test_new_fog_collector_orientation_is_a_cardinal_point(admin_client):
    url = "/api/v1/fog-collectors"
    assert admin_client.post(url, json={"code": "AN-x", "name": "Prueba", "orientation": "al cerro"}).status_code == 422
    assert admin_client.post(url, json={"code": "AN-y", "name": "Prueba", "orientation": "NE"}).status_code == 201


def _maintenance(admin_client, station, final_status, *, sensor=True):
    payload = {
        "device_id": station["device"]["id"],
        "sensor_id": station["sensor"]["id"] if sensor else None,
        "performed_at": "2026-11-01T12:00:00Z",
        "maintenance_type": "correctivo",
        "description": "Revisión del componente",
        "final_status": final_status,
    }
    response = admin_client.post("/api/v1/maintenance", json=payload)
    assert response.status_code == 201, response.text


def test_final_status_moves_the_sensor_out_of_service_and_back(admin_client, station):
    sensor_url = f"/api/v1/sensors/{station['sensor']['id']}"
    _maintenance(admin_client, station, "fuera_de_servicio")
    assert admin_client.get(sensor_url).json()["status"] == "mantenimiento"
    _maintenance(admin_client, station, "operativo")
    assert admin_client.get(sensor_url).json()["status"] == "activo"
    _maintenance(admin_client, station, "reemplazado")
    assert admin_client.get(sensor_url).json()["status"] == "inactivo"
    _maintenance(admin_client, station, "operativo")  # un retirado solo lo reactiva el administrador
    assert admin_client.get(sensor_url).json()["status"] == "inactivo"


def test_final_status_without_sensor_applies_to_the_device(admin_client, station):
    _maintenance(admin_client, station, "fuera_de_servicio", sensor=False)
    assert admin_client.get(f"/api/v1/devices/{station['device']['id']}").json()["status"] == "mantenimiento"
    assert admin_client.get(f"/api/v1/sensors/{station['sensor']['id']}").json()["status"] == "activo"
