import io
from datetime import UTC, datetime, timedelta

import pytest
from openpyxl import load_workbook

from tests.test_iot import BATCH, batch, headers, reading, station  # noqa: F401

EXPORT = "/api/v1/reports/export"


@pytest.fixture
def with_data(client, station):  # noqa: F811
    base = datetime.now(UTC) - timedelta(days=1)
    client.post(
        BATCH,
        json=batch(
            reading("vol", 1.5, "L", measured_at=base),
            reading("vol", 2.5, "L", measured_at=base + timedelta(minutes=5)),
            reading("hum", None, "%", measured_at=base),
            reading("temp", 12, "C", measured_at=base),
        ),
        headers=headers(station),
    )
    return station


@pytest.mark.parametrize(
    ("fmt", "content_type", "magic"),
    [
        ("csv", "text/csv", b"\xef\xbb\xbf"),
        ("xlsx", "application/vnd.openxml", b"PK"),
        ("pdf", "application/pdf", b"%PDF"),
    ],
)
def test_measurement_report_formats(admin_client, with_data, fmt, content_type, magic):
    response = admin_client.get(EXPORT, params={"report": "mediciones", "format": fmt})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith(content_type)
    assert "attachment" in response.headers["content-disposition"]
    assert response.content.startswith(magic)


def test_csv_keeps_unmeasured_values_empty(admin_client, with_data):
    text = admin_client.get(EXPORT, params={"report": "mediciones", "format": "csv"}).text
    hum_row = next(line for line in text.splitlines() if "Humedad" in line)
    assert ",," in hum_row  # valor vacío, no 0


def test_volume_report_sums_incremental_values(admin_client, with_data):
    response = admin_client.get(EXPORT, params={"report": "volumen", "format": "xlsx", "bucket": "month"})
    ws = load_workbook(io.BytesIO(response.content)).active
    values = [row[1] for row in ws.iter_rows(values_only=True) if isinstance(row[1], (int, float))]
    assert sum(values) == pytest.approx(4.0)


@pytest.mark.parametrize("kind", ["inventario_stock", "inventario_movimientos", "mantenimientos"])
def test_other_reports(admin_client, kind):
    assert admin_client.get(EXPORT, params={"report": kind, "format": "pdf"}).status_code == 200


def test_variable_report_requires_sensor_type(admin_client):
    response = admin_client.get(EXPORT, params={"report": "variable", "format": "csv"})
    assert response.json()["error"]["code"] == "variable_requerida"
    assert "Variable" in response.json()["error"]["message"]


def test_report_permissions_and_audit(make_client, factory, admin_client):
    observer = factory.client_for(make_client(), "obs-rep", ["docente"])
    assert observer.get(EXPORT, params={"report": "mediciones"}).status_code == 403
    director = factory.client_for(make_client(), "dir-rep", ["director"])
    assert director.get(EXPORT, params={"report": "mediciones", "format": "csv"}).status_code == 200
    logs = admin_client.get("/api/v1/admin/audit-logs", params={"action": "reporte.exportar"}).json()
    assert logs["total"] == 1


CATALOG = "/api/v1/reports/catalog"


def sheet_lines(response):
    """Encabezado (columna A) y filas de datos del Excel generado."""
    rows = list(load_workbook(io.BytesIO(response.content)).active.iter_rows(values_only=True))
    header_index = next(i for i, r in enumerate(rows) if r[0] is not None and i > 0 and r[1] is not None)
    return [r[0] for r in rows[1:header_index] if r[0]], rows[header_index], rows[header_index + 1 :]


def test_catalog_groups_reports_by_module_and_permission(admin_client, make_client, factory):
    admin = admin_client.get(CATALOG).json()
    assert {r["module"] for r in admin} == {
        "Monitoreo IoT y volumen",
        "Inventario",
        "Mantenimiento",
        "Reportes de incidencia",
        "Usuarios y auditoría",
    }
    kardex = next(r for r in admin if r["kind"] == "inventario_kardex")
    assert {"key": "item_id", "label": "Repuesto", "required": True} in kardex["filters"]

    director = factory.client_for(make_client(), "dir-cat", ["director"])
    kinds = {r["kind"] for r in director.get(CATALOG).json()}
    assert "incidencias" in kinds and "mantenimientos" in kinds
    assert not kinds & {"usuarios", "auditoria"}  # datos personales y auditoría: solo administración
    assert director.get(EXPORT, params={"report": "usuarios"}).status_code == 403
    assert director.get(EXPORT, params={"report": "auditoria"}).status_code == 403

    teacher = factory.client_for(make_client(), "doc-cat", ["docente"])
    assert teacher.get(CATALOG).status_code == 403


@pytest.mark.parametrize("kind", ["dispositivos", "incidencias", "usuarios", "auditoria", "inventario_consumo"])
def test_new_reports_render(admin_client, kind):
    for fmt in ("pdf", "xlsx", "csv"):
        response = admin_client.get(EXPORT, params={"report": kind, "format": fmt})
        assert response.status_code == 200, response.text


def test_stock_report_filters_and_describes_them(admin_client):
    categories = {c["name"]: c["id"] for c in admin_client.get("/api/v1/inventory/categories").json()}
    for code, category, stock in [
        ("LOW1", "Consumibles", "1"),
        ("OK1", "Consumibles", "9"),
        ("HW1", "Herramientas", "0"),
    ]:
        admin_client.post(
            "/api/v1/inventory/items",
            json={
                "code": code,
                "name": code,
                "category_id": categories[category],
                "unit": "unidad",
                "min_stock": "2",
                "initial_stock": stock,
            },
        )
    response = admin_client.get(
        EXPORT,
        params={
            "report": "inventario_stock",
            "format": "xlsx",
            "category_id": categories["Consumibles"],
            "low_stock_only": "true",
        },
    )
    header, _columns, rows = sheet_lines(response)
    assert [r[0] for r in rows] == ["LOW1"]
    assert "Categoría: Consumibles" in header
    assert "Solo stock bajo: sí" in header


def test_maintenance_report_filters_by_origin_and_responsible(admin_client, make_client, factory):
    device = admin_client.post("/api/v1/devices", json={"code": "esp32-50", "name": "Estación 50"}).json()["device"]
    teacher = factory.client_for(make_client(), "doc-mt", ["docente"])
    technician = factory.client_for(make_client(), "tec-mt", ["mantenimiento"])
    work = {"maintenance_type": "limpieza", "description": "Limpieza general.", "final_status": "operativo"}
    admin_client.post(
        "/api/v1/maintenance",
        json=work | {"device_id": device["id"], "performed_at": datetime.now(UTC).isoformat()},
    )
    incident = teacher.post(
        "/api/v1/incidents",
        json={"title": "Malla rota sur", "description": "La malla tiene un desgarro.", "device_id": device["id"]},
    ).json()
    for step in ("accept", "start"):
        technician.post(f"/api/v1/incidents/{incident['id']}/{step}")
    technician.post(f"/api/v1/incidents/{incident['id']}/finish", json=work)
    tech_id = technician.get("/api/v1/auth/me").json()["id"]

    def rows(**params):
        response = admin_client.get(EXPORT, params={"report": "mantenimientos", "format": "xlsx", **params})
        return sheet_lines(response)

    assert len(rows()[2]) == 2
    header, _, from_incident = rows(origin="incidencia")
    assert [r[-1] for r in from_incident] == [f"#{incident['id']}"]
    assert "Origen: Atención de reportes de incidencia" in header
    header, _, by_tech = rows(responsible_id=tech_id)
    assert len(by_tech) == 1
    assert "Responsable: Usuario Tec-mt" in header
    assert rows(origin="directo")[2][0][-1] is None

    # Reporte de incidencias: estado y tiempos de atención.
    response = admin_client.get(
        EXPORT, params={"report": "incidencias", "format": "xlsx", "incident_status": "finalizado"}
    )
    header, columns, incident_rows = sheet_lines(response)
    assert len(incident_rows) == 1
    assert incident_rows[0][columns.index("Asignado a")] == "Usuario Tec-mt"
    assert incident_rows[0][columns.index("Horas hasta finalizar")] is not None
    assert "Estado del reporte: finalizado" in header
    empty = admin_client.get(EXPORT, params={"report": "incidencias", "format": "xlsx", "incident_status": "abierto"})
    assert sheet_lines(empty)[2] == []

    options = admin_client.get("/api/v1/reports/filter-options").json()
    assert tech_id in [p["id"] for p in options["responsibles"]]
    assert "incidencia.finalizar" in options["audit_actions"]


def test_audit_report_filters_by_module_prefix(admin_client):
    admin_client.post("/api/v1/devices", json={"code": "esp32-60", "name": "Estación 60"})
    response = admin_client.get(EXPORT, params={"report": "auditoria", "format": "xlsx", "action": "dispositivo"})
    _, columns, rows = sheet_lines(response)
    actions = {r[columns.index("Acción")] for r in rows}
    assert actions and all(a.startswith("dispositivo.") for a in actions)


def test_users_report_filters_by_role(admin_client, factory):
    factory.user("doc-u1", roles=["docente"])
    factory.user("dir-u1", roles=["director"])
    roles = {r["name"]: r["id"] for r in admin_client.get("/api/v1/roles").json()}
    response = admin_client.get(EXPORT, params={"report": "usuarios", "format": "xlsx", "role_id": roles["docente"]})
    header, _, rows = sheet_lines(response)
    assert [r[0] for r in rows] == ["doc-u1"]
    assert "Rol: docente" in header
