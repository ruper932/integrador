"""Reportes de incidencia: docente reporta → mantenimiento acepta, inicia y finaliza."""

import pytest
from sqlalchemy import select

from app.data.models.inventory import InventoryMovement
from app.data.models.security import AuditLog

INCIDENTS = "/api/v1/incidents"


@pytest.fixture
def station(admin_client):
    device = admin_client.post("/api/v1/devices", json={"code": "esp32-20", "name": "Estación 20"}).json()["device"]
    types = {t["code"]: t["id"] for t in admin_client.get("/api/v1/sensor-types").json()}
    sensor = admin_client.post(
        "/api/v1/sensors", json={"device_id": device["id"], "sensor_type_id": types["temperatura"], "code": "temp"}
    ).json()
    category = next(c["id"] for c in admin_client.get("/api/v1/inventory/categories").json())
    item = admin_client.post(
        "/api/v1/inventory/items",
        json={"code": "SELLO", "name": "Silicona", "category_id": category, "unit": "unidad", "initial_stock": "3"},
    ).json()
    return {"device": device, "sensor": sensor, "item": item}


@pytest.fixture
def people(make_client, factory, admin_client):
    return {
        "docente": factory.client_for(make_client(), "docente1", ["docente"]),
        "docente2": factory.client_for(make_client(), "docente2", ["docente"]),
        "director": factory.client_for(make_client(), "directora", ["director"]),
        "tecnico": factory.client_for(make_client(), "tecnico1", ["mantenimiento"]),
        "tecnico2": factory.client_for(make_client(), "tecnico2", ["mantenimiento"]),
        "admin": admin_client,
    }


def report(client, station=None, **overrides):
    payload = {
        "title": "Malla rota en el atrapanieblas",
        "description": "La malla tiene un desgarro grande en la parte superior.",
        "priority": "alta",
        "device_id": station["device"]["id"] if station else None,
    } | overrides
    response = client.post(INCIDENTS, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def finish_payload(**overrides):
    return {
        "maintenance_type": "correctivo",
        "description": "Se cosió la malla y se reforzaron las abrazaderas.",
        "final_status": "operativo",
    } | overrides


def unread(client):
    return client.get("/api/v1/notifications").json()


def test_full_flow_is_visible_to_reporter_supervisors_and_deducts_stock(people, station, db):
    created = report(people["docente"], station)
    assert created["status"] == "abierto"
    assert created["assignee"] is None
    assert created["reporter"]["username"] == "docente1"

    # El personal de mantenimiento recibe la alerta del nuevo reporte.
    alert = unread(people["tecnico"])
    assert alert["unread"] == 1
    assert alert["items"][0]["incident_report_id"] == created["id"]
    assert "Malla rota" in alert["items"][0]["message"]
    assert unread(people["docente"])["unread"] == 0  # quien reporta no se avisa a sí mismo
    open_ids = [r["id"] for r in people["tecnico"].get(INCIDENTS, params={"scope": "open"}).json()["items"]]
    assert open_ids == [created["id"]]

    accepted = people["tecnico"].post(f"{INCIDENTS}/{created['id']}/accept")
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["status"] == "aceptado"
    assert body["assignee"]["username"] == "tecnico1"
    assert body["maintenance"]["status"] == "aceptado"
    assert body["maintenance"]["device_id"] == station["device"]["id"]  # se copia del reporte

    # El docente ve el estado y el nombre del personal asignado, y recibe el aviso.
    mine = people["docente"].get(INCIDENTS, params={"scope": "mine"}).json()["items"][0]
    assert mine["status"] == "aceptado"
    assert mine["assignee"]["full_name"] == "Usuario Tecnico1"
    assert unread(people["docente"])["items"][0]["title"] == "Su reporte fue aceptado"

    started = people["tecnico"].post(f"{INCIDENTS}/{created['id']}/start").json()
    assert started["status"] == "en_progreso"
    assert started["maintenance"]["started_at"] is not None

    finished = people["tecnico"].post(
        f"{INCIDENTS}/{created['id']}/finish",
        json=finish_payload(parts=[{"item_id": station["item"]["id"], "quantity": "2"}]),
    )
    assert finished.status_code == 200, finished.text
    result = finished.json()
    assert result["status"] == "finalizado"
    record = result["maintenance"]
    assert record["final_status"] == "operativo"
    assert record["performed_at"] == record["finished_at"]
    assert record["items"][0]["quantity"] == "2.000"
    movement = db.get(InventoryMovement, record["items"][0]["movement_id"])
    assert movement.movement_type.code == "salida_mantenimiento"
    assert movement.maintenance_record_id == record["id"]
    stock = people["admin"].get(f"/api/v1/inventory/items/{station['item']['id']}").json()["current_stock"]
    assert stock == "1.000"
    assert people["docente"].get(f"{INCIDENTS}/{created['id']}").json()["status"] == "finalizado"
    assert [n["title"] for n in unread(people["docente"])["items"]] == [
        "Su reporte fue atendido",
        "Mantenimiento en progreso",
        "Su reporte fue aceptado",
    ]

    # Administrador y director ven todo el proceso.
    for supervisor in (people["admin"], people["director"]):
        all_reports = supervisor.get(INCIDENTS, params={"scope": "all"}).json()
        assert [r["status"] for r in all_reports["items"]] == ["finalizado"]
        assert supervisor.get("/api/v1/maintenance", params={"status": "finalizado"}).json()["total"] == 1
    summary = people["director"].get(f"{INCIDENTS}/summary").json()
    assert summary["all"] == {"finalizado": 1}

    actions = set(db.scalars(select(AuditLog.action).where(AuditLog.entity_type == "incident_report")))
    assert actions == {"incidencia.reportar", "incidencia.aceptar", "incidencia.iniciar", "incidencia.finalizar"}


def test_permissions_per_role(people, station):
    created = report(people["docente"], station)
    url = f"{INCIDENTS}/{created['id']}"

    assert people["tecnico"].post(INCIDENTS, json={"title": "x"}).status_code == 403
    assert people["docente"].post(f"{url}/accept").status_code == 403
    assert people["director"].post(f"{url}/accept").status_code == 403
    assert people["docente"].get(INCIDENTS, params={"scope": "all"}).status_code == 403
    assert people["tecnico"].get(INCIDENTS, params={"scope": "all"}).status_code == 403
    assert people["director"].get(INCIDENTS, params={"scope": "open"}).status_code == 403
    # Otro docente no puede ver un reporte ajeno (ni saber que existe).
    assert people["docente2"].get(url).status_code == 404
    assert people["docente2"].get(INCIDENTS, params={"scope": "mine"}).json()["total"] == 0
    assert people["director"].get(url).status_code == 200


def test_transitions_follow_the_order_and_only_the_assignee_advances(people, station):
    created = report(people["docente"], station)
    url = f"{INCIDENTS}/{created['id']}"

    assert people["tecnico"].post(f"{url}/start").json()["error"]["code"] == "transicion_invalida"
    assert people["tecnico"].post(f"{url}/accept").status_code == 200
    again = people["tecnico2"].post(f"{url}/accept")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "reporte_ya_aceptado"

    assert people["tecnico2"].post(f"{url}/start").status_code == 403
    early = people["tecnico"].post(f"{url}/finish", json=finish_payload())
    assert early.json()["error"]["code"] == "transicion_invalida"
    assert people["tecnico"].post(f"{url}/start").status_code == 200
    assert people["tecnico"].post(f"{url}/start").json()["error"]["code"] == "transicion_invalida"
    assert people["tecnico2"].post(f"{url}/finish", json=finish_payload()).status_code == 403
    assert people["tecnico"].post(f"{url}/finish", json=finish_payload()).status_code == 200
    assert people["tecnico"].post(f"{url}/finish", json=finish_payload()).json()["error"]["code"] == (
        "transicion_invalida"
    )


def test_finish_without_stock_keeps_the_maintenance_in_progress(people, station):
    created = report(people["docente"], station)
    url = f"{INCIDENTS}/{created['id']}"
    people["tecnico"].post(f"{url}/accept")
    people["tecnico"].post(f"{url}/start")

    response = people["tecnico"].post(
        f"{url}/finish", json=finish_payload(parts=[{"item_id": station["item"]["id"], "quantity": "10"}])
    )
    assert response.json()["error"]["code"] == "stock_insuficiente"
    current = people["tecnico"].get(url).json()
    assert current["status"] == "en_progreso"
    assert current["maintenance"]["items"] == []
    assert people["admin"].get(f"/api/v1/inventory/items/{station['item']['id']}").json()["current_stock"] == "3.000"


def test_report_without_device_requires_it_when_finishing(people, station):
    created = report(people["docente"], None, location_reference="Junto al tanque principal")
    assert created["device_id"] is None
    url = f"{INCIDENTS}/{created['id']}"
    people["tecnico"].post(f"{url}/accept")
    people["tecnico"].post(f"{url}/start")

    missing = people["tecnico"].post(f"{url}/finish", json=finish_payload())
    assert missing.json()["error"]["code"] == "dispositivo_requerido"
    done = people["tecnico"].post(
        f"{url}/finish",
        json=finish_payload(device_id=station["device"]["id"], sensor_id=station["sensor"]["id"]),
    )
    assert done.status_code == 200
    assert done.json()["maintenance"]["sensor_code"] == "temp"


def test_report_validations(people, station, admin_client):
    other = admin_client.post("/api/v1/devices", json={"code": "esp32-21", "name": "Otra"}).json()["device"]
    teacher = people["docente"]
    base = {"title": "Sensor sin datos", "description": "El sensor no envía datos desde ayer."}

    wrong = teacher.post(INCIDENTS, json=base | {"device_id": other["id"], "sensor_id": station["sensor"]["id"]})
    assert wrong.json()["error"]["code"] == "sensor_no_asociado"
    no_device = teacher.post(INCIDENTS, json=base | {"sensor_id": station["sensor"]["id"]})
    assert no_device.json()["error"]["code"] == "dispositivo_requerido"
    assert teacher.post(INCIDENTS, json=base | {"title": "   ab  "}).status_code == 422
    assert teacher.post(INCIDENTS, json=base | {"priority": "urgente"}).status_code == 422
    assert teacher.post(INCIDENTS, json=base | {"device_id": 99999}).json()["error"]["code"] == (
        "referencia_inexistente"
    )


def test_open_inbox_lists_urgent_first(people):
    low = report(people["docente"], None, priority="baja", title="Revisar pintura del poste")
    high = report(people["docente"], None, priority="alta", title="Cable cortado en la estación")
    inbox = people["tecnico"].get(INCIDENTS, params={"scope": "open"}).json()["items"]
    assert [r["id"] for r in inbox] == [high["id"], low["id"]]
    summary = people["tecnico"].get(f"{INCIDENTS}/summary").json()
    assert summary["open"] == 2
    assert summary["all"] is None


def test_notifications_belong_to_their_user(people):
    report(people["docente"], None)
    notifications = unread(people["tecnico"])
    notification_id = notifications["items"][0]["id"]

    assert people["tecnico2"].post(f"/api/v1/notifications/{notification_id}/read").status_code == 404
    assert people["tecnico"].post(f"/api/v1/notifications/{notification_id}/read").status_code == 200
    assert unread(people["tecnico"])["unread"] == 0
    assert unread(people["tecnico2"])["unread"] == 1
    people["tecnico2"].post("/api/v1/notifications/read-all")
    assert unread(people["tecnico2"])["unread"] == 0
    assert len(unread(people["tecnico2"])["items"]) == 1  # se marca como leída, no se elimina


def alerts(client):
    response = client.get(f"{INCIDENTS}/alerts")
    assert response.status_code == 200, response.text
    return {kind: [a["id"] for a in items] for kind, items in response.json().items()}


def test_high_alert_blocks_until_reviewed_and_medium_is_reminded_until_accepted(people, db):
    high = report(people["docente"], None, priority="alta")
    medium = report(people["docente"], None, priority="media", title="Lecturas extrañas del sensor")
    report(people["docente"], None, priority="baja", title="Pintura del poste gastada")

    assert alerts(people["tecnico"]) == {"blocking": [high["id"]], "reminders": [medium["id"]]}
    assert alerts(people["docente"]) == {"blocking": [], "reminders": []}  # quien reporta no recibe la alerta

    assert people["tecnico"].post(f"{INCIDENTS}/{high['id']}/review").status_code == 200
    assert people["tecnico"].post(f"{INCIDENTS}/{medium['id']}/review").status_code == 200
    # Revisar desbloquea solo a ese usuario; el recordatorio de la media sigue hasta que se acepte.
    assert alerts(people["tecnico"]) == {"blocking": [], "reminders": [medium["id"]]}
    assert alerts(people["tecnico2"])["blocking"] == [high["id"]]
    reviews = db.scalars(select(AuditLog.entity_id).where(AuditLog.action == "incidencia.revisar_alerta")).all()
    assert sorted(reviews) == sorted([str(high["id"]), str(medium["id"])])

    people["tecnico2"].post(f"{INCIDENTS}/{high['id']}/accept")
    people["tecnico2"].post(f"{INCIDENTS}/{medium['id']}/accept")
    assert alerts(people["tecnico"]) == alerts(people["tecnico2"]) == {"blocking": [], "reminders": []}


def test_review_alert_of_a_hidden_report_is_not_found(people):
    high = report(people["docente"], None)
    assert people["docente2"].post(f"{INCIDENTS}/{high['id']}/review").status_code == 404
    assert people["tecnico"].post(f"{INCIDENTS}/999999/review").status_code == 404
