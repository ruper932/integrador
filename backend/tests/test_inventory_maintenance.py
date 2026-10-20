from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.data.models.inventory import InventoryMovement, MaintenanceRecord

ITEMS = "/api/v1/inventory/items"


def category_id(client, name="Sensores ambientales"):
    return next(c["id"] for c in client.get("/api/v1/inventory/categories").json() if c["name"] == name)


@pytest.fixture
def device(admin_client):
    fog = admin_client.post("/api/v1/fog-collectors", json={"code": "AN-09", "name": "Atrapanieblas 9"}).json()
    created = admin_client.post(
        "/api/v1/devices", json={"code": "esp32-09", "name": "Estación 9", "fog_collector_id": fog["id"]}
    ).json()["device"]
    types = {t["code"]: t["id"] for t in admin_client.get("/api/v1/sensor-types").json()}
    sensor = admin_client.post(
        "/api/v1/sensors",
        json={"device_id": created["id"], "sensor_type_id": types["temperatura"], "code": "temp"},
    ).json()
    return {"device": created, "sensor": sensor}


@pytest.fixture
def item(admin_client, device):
    response = admin_client.post(
        ITEMS,
        json={
            "code": "DHT22",
            "name": "Sensor DHT22",
            "category_id": category_id(admin_client),
            "unit": "unidad",
            "min_stock": "2",
            "initial_stock": "5",
            "compatible_sensor_ids": [device["sensor"]["id"]],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_seeded_categories(admin_client):
    names = {c["name"] for c in admin_client.get("/api/v1/inventory/categories").json()}
    assert {"Microcontroladores", "Sensores hídricos", "Consumibles", "Herramientas"} <= names


def test_initial_stock_creates_traceable_entry(admin_client, item):
    assert Decimal(item["current_stock"]) == 5
    assert item["compatibilities"][0]["sensor_id"] is not None
    movements = admin_client.get(f"{ITEMS}/{item['id']}/movements").json()["items"]
    assert len(movements) == 1
    entry = movements[0]
    assert entry["movement_type"]["code"] == "entrada"
    assert entry["username"] == "admin"
    assert entry["reason"] == "Stock inicial"


def test_entries_and_exits_update_stock(admin_client, item):
    url = f"{ITEMS}/{item['id']}/movements"
    assert (
        admin_client.post(url, json={"movement_type": "entrada", "quantity": "3", "reason": "Compra"}).status_code
        == 201
    )
    out = admin_client.post(url, json={"movement_type": "salida", "quantity": "6", "reason": "Préstamo a otra sede"})
    assert out.json()["stock_before"] == "8.000"
    assert out.json()["stock_after"] == "2.000"
    assert admin_client.get(f"{ITEMS}/{item['id']}").json()["current_stock"] == "2.000"


def test_exit_greater_than_stock_is_rejected(admin_client, item):
    url = f"{ITEMS}/{item['id']}/movements"
    response = admin_client.post(url, json={"movement_type": "salida", "quantity": "5.5", "reason": "Exceso"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "stock_insuficiente"
    assert admin_client.get(f"{ITEMS}/{item['id']}").json()["current_stock"] == "5.000"


def test_invalid_quantities_and_system_movement_types(admin_client, item):
    url = f"{ITEMS}/{item['id']}/movements"
    assert (
        admin_client.post(url, json={"movement_type": "entrada", "quantity": "0", "reason": "nada"}).status_code == 422
    )
    assert (
        admin_client.post(url, json={"movement_type": "salida", "quantity": "-1", "reason": "neg"}).status_code == 422
    )
    manual = admin_client.post(url, json={"movement_type": "salida_mantenimiento", "quantity": "1", "reason": "x"})
    assert manual.status_code == 422


def test_low_stock_alert(admin_client, item):
    url = f"{ITEMS}/{item['id']}/movements"
    assert admin_client.get("/api/v1/inventory/alerts/low-stock").json() == []
    admin_client.post(url, json={"movement_type": "salida", "quantity": "3", "reason": "Reemplazos"})
    alerts = admin_client.get("/api/v1/inventory/alerts/low-stock").json()
    assert [a["code"] for a in alerts] == ["DHT22"]
    assert alerts[0]["low_stock"] is True


def test_items_are_deactivated_not_deleted(admin_client, item):
    response = admin_client.delete(f"{ITEMS}/{item['id']}")
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert admin_client.get(f"{ITEMS}/{item['id']}").status_code == 200
    movement = admin_client.post(
        f"{ITEMS}/{item['id']}/movements", json={"movement_type": "entrada", "quantity": "1", "reason": "Compra"}
    )
    assert movement.json()["error"]["code"] == "repuesto_inactivo"


def test_filter_items_by_compatible_sensor(admin_client, item, device):
    found = admin_client.get(ITEMS, params={"sensor_id": device["sensor"]["id"]}).json()
    assert [i["code"] for i in found["items"]] == ["DHT22"]
    assert admin_client.get(ITEMS, params={"device_id": device["device"]["id"]}).json()["total"] == 0


def test_stock_report_csv(admin_client, item):
    response = admin_client.get("/api/v1/inventory/reports/stock", params={"format": "csv"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "DHT22" in response.text


def maintenance_payload(device, **overrides):
    payload = {
        "device_id": device["device"]["id"],
        "sensor_id": device["sensor"]["id"],
        "performed_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        "maintenance_type": "reemplazo",
        "description": "Reemplazo del sensor de temperatura dañado por humedad",
        "final_status": "operativo",
        "parts": [],
    }
    payload.update(overrides)
    return payload


def test_maintenance_with_parts_creates_inventory_exit(admin_client, item, device, db):
    payload = maintenance_payload(device, parts=[{"item_id": item["id"], "quantity": "2"}])
    response = admin_client.post("/api/v1/maintenance", json=payload)
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["username"] == "admin"
    assert record["items"][0]["item_code"] == "DHT22"
    assert admin_client.get(f"{ITEMS}/{item['id']}").json()["current_stock"] == "3.000"

    movement = db.get(InventoryMovement, record["items"][0]["movement_id"])
    assert movement.movement_type.code == "salida_mantenimiento"
    assert movement.maintenance_record_id == record["id"]
    assert admin_client.get(f"/api/v1/maintenance/{record['id']}").status_code == 200


def test_maintenance_with_insufficient_stock_is_rolled_back(admin_client, item, device, db):
    payload = maintenance_payload(device, parts=[{"item_id": item["id"], "quantity": "50"}])
    response = admin_client.post("/api/v1/maintenance", json=payload)
    assert response.json()["error"]["code"] == "stock_insuficiente"
    assert db.scalars(select(MaintenanceRecord)).all() == []
    assert admin_client.get(f"{ITEMS}/{item['id']}").json()["current_stock"] == "5.000"


def test_maintenance_validations(admin_client, item, device):
    no_parts = admin_client.post("/api/v1/maintenance", json=maintenance_payload(device))
    assert no_parts.json()["error"]["code"] == "repuestos_requeridos"

    unknown_part = admin_client.post(
        "/api/v1/maintenance", json=maintenance_payload(device, parts=[{"item_id": 99999, "quantity": "1"}])
    )
    assert unknown_part.status_code == 404

    other = admin_client.post("/api/v1/devices", json={"code": "esp32-10", "name": "Otra"}).json()["device"]
    wrong_sensor = admin_client.post(
        "/api/v1/maintenance", json=maintenance_payload(device, device_id=other["id"], maintenance_type="limpieza")
    )
    assert wrong_sensor.json()["error"]["code"] == "sensor_no_asociado"

    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    in_future = admin_client.post(
        "/api/v1/maintenance", json=maintenance_payload(device, maintenance_type="limpieza", performed_at=future)
    )
    assert in_future.json()["error"]["code"] == "fecha_futura"


def test_maintenance_permission_must_be_assigned(make_client, factory, admin_client, device):
    director = factory.client_for(make_client(), "profe", ["director"])
    payload = maintenance_payload(device, maintenance_type="inspeccion")
    assert director.get("/api/v1/maintenance").status_code == 200
    assert director.post("/api/v1/maintenance", json=payload).status_code == 403

    technician = factory.client_for(make_client(), "tecnico", ["director", "mantenimiento"])
    assert technician.post("/api/v1/maintenance", json=payload).status_code == 201
