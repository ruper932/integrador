"""Los listados aceptan los mismos filtros que el reporte de su módulo (la vista y la exportación coinciden)."""

from tests.test_incidents import finish_payload, people, report, station  # noqa: F401 - fixtures reutilizadas

INCIDENTS = "/api/v1/incidents"


def ids(response):
    assert response.status_code == 200, response.text
    return {row["id"] for row in response.json()["items"]}


def test_incident_list_filters_and_scope_rules(people, station):  # noqa: F811
    high = report(people["docente"], station, priority="alta")
    low = report(people["docente2"], None, priority="baja")
    director = people["director"]

    assert ids(director.get(INCIDENTS, params={"scope": "all", "priority": "alta"})) == {high["id"]}
    assert ids(director.get(INCIDENTS, params={"scope": "all", "device_id": station["device"]["id"]})) == {high["id"]}
    reporter = low["reporter"]["id"]
    assert ids(director.get(INCIDENTS, params={"scope": "all", "reporter_id": reporter})) == {low["id"]}
    # «Mis reportes» siempre son los propios: un filtro de autor no lo amplía a reportes ajenos.
    mine = people["docente"].get(INCIDENTS, params={"scope": "mine", "reporter_id": reporter})
    assert ids(mine) == {high["id"]}


def test_maintenance_list_filters(people, station):  # noqa: F811
    tecnico = people["tecnico"]
    incident = report(people["docente"], station)
    tecnico.post(f"{INCIDENTS}/{incident['id']}/accept")
    tecnico.post(f"{INCIDENTS}/{incident['id']}/start")
    tecnico.post(f"{INCIDENTS}/{incident['id']}/finish", json=finish_payload(final_status="fuera_de_servicio"))
    record = tecnico.get(f"{INCIDENTS}/{incident['id']}").json()["maintenance"]["id"]
    admin = people["admin"]

    assert ids(admin.get("/api/v1/maintenance", params={"final_status": "fuera_de_servicio"})) == {record}
    assert ids(admin.get("/api/v1/maintenance", params={"final_status": "operativo"})) == set()
    assert ids(admin.get("/api/v1/maintenance", params={"origin": "incidencia"})) == {record}
    assert ids(admin.get("/api/v1/maintenance", params={"origin": "directo"})) == set()
    tecnico_id = tecnico.get("/api/v1/auth/me").json()["id"]
    assert ids(admin.get("/api/v1/maintenance", params={"responsible_id": tecnico_id})) == {record}


def test_user_list_filters_by_role(admin_client, factory):
    factory.user("tecnico9", roles=["mantenimiento"])
    role = next(r["id"] for r in admin_client.get("/api/v1/roles").json() if r["name"] == "mantenimiento")
    names = [u["username"] for u in admin_client.get("/api/v1/users", params={"role_id": role}).json()["items"]]
    assert names == ["tecnico9"]


def test_device_list_filters(admin_client):
    fog = admin_client.post("/api/v1/fog-collectors", json={"code": "AN-9", "name": "Norte"}).json()
    linked = admin_client.post(
        "/api/v1/devices", json={"code": "esp32-91", "name": "Con malla", "fog_collector_id": fog["id"]}
    ).json()["device"]
    other = admin_client.post("/api/v1/devices", json={"code": "esp32-92", "name": "Sin malla"}).json()["device"]
    admin_client.put(f"/api/v1/devices/{other['id']}", json={"status": "mantenimiento"})

    by_fog = admin_client.get("/api/v1/devices", params={"fog_collector_id": fog["id"]}).json()
    assert [d["id"] for d in by_fog] == [linked["id"]]
    by_status = admin_client.get("/api/v1/devices", params={"status": "mantenimiento"}).json()
    assert [d["id"] for d in by_status] == [other["id"]]


def test_item_list_filters(admin_client):
    category = next(c["id"] for c in admin_client.get("/api/v1/inventory/categories").json())

    def item(code, stock, minimum, condition="nuevo"):
        payload = {
            "code": code,
            "name": code,
            "category_id": category,
            "unit": "unidad",
            "initial_stock": stock,
            "min_stock": minimum,
            "condition": condition,
        }
        response = admin_client.post("/api/v1/inventory/items", json=payload)
        assert response.status_code == 201, response.text
        return response.json()["id"]

    low = item("BAJO", "1", "2")
    used = item("USADO", "5", "1", condition="usado")
    retired = item("RETIRADO", "5", "1")
    admin_client.delete(f"/api/v1/inventory/items/{retired}")
    items = "/api/v1/inventory/items"

    assert ids(admin_client.get(items, params={"low_stock_only": True})) == {low}
    assert ids(admin_client.get(items, params={"condition": "usado"})) == {used}
    assert retired not in ids(admin_client.get(items))
    assert retired in ids(admin_client.get(items, params={"include_inactive": True}))
