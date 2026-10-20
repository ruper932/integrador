"""Incidencias automáticas: estación sin comunicación y sensor con lecturas anómalas."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.business.services.auto_incident_service import AutoIncidentService
from app.core.clock import utcnow
from app.core.config import get_settings
from app.data.models.incidents import IncidentReport
from app.data.models.iot import Device
from app.data.models.security import AuditLog
from tests.test_iot import BATCH, batch, headers, reading, station  # noqa: F401 - fixture reutilizada

INCIDENTS = "/api/v1/incidents"
FINISH = {
    "maintenance_type": "correctivo",
    "description": "Se cambió la fuente del ESP32.",
    "final_status": "operativo",
}


@pytest.fixture
def people(make_client, factory, admin_client):
    return {
        "tecnico": factory.client_for(make_client(), "tecnico1", ["mantenimiento"]),
        "director": factory.client_for(make_client(), "directora", ["director"]),
        "docente": factory.client_for(make_client(), "docente1", ["docente"]),
    }


def silence(db, station, hours):  # noqa: F811
    device = db.get(Device, station["device"]["id"])
    device.last_seen_at = utcnow() - timedelta(hours=hours)
    db.flush()


def auto_reports(db):
    return db.scalars(select(IncidentReport).where(IncidentReport.source == "sistema")).all()


def test_silent_station_opens_one_report_and_notifies(db, station, people):  # noqa: F811
    silence(db, station, get_settings().auto_incident_offline_hours + 1)

    created = AutoIncidentService(db).run()

    assert len(created) == 1
    report = created[0]
    assert (report.auto_cause, report.priority, report.reported_by_id) == ("sin_comunicacion", "alta", None)
    assert report.device_id == station["device"]["id"]
    for who in ("tecnico", "director"):
        titles = [n["title"] for n in people[who].get("/api/v1/notifications").json()["items"]]
        assert "Incidencia detectada por el sistema" in titles
    # El docente no atiende ni supervisa: no recibe el aviso.
    assert people["docente"].get("/api/v1/notifications").json()["items"] == []
    assert db.scalars(select(AuditLog).where(AuditLog.action == "incidencia.reportar_automatica")).one().user_id is None

    # Una segunda pasada no duplica el reporte mientras siga pendiente.
    assert AutoIncidentService(db).run() == []


def test_communicating_or_non_active_station_is_ignored(db, client, admin_client, station):  # noqa: F811
    body = client.post(BATCH, json=batch(reading("temp", 12, "C")), headers=headers(station)).json()
    assert body["accepted"] == 1
    assert AutoIncidentService(db).run() == []

    silence(db, station, 100)
    admin_client.put(f"/api/v1/devices/{station['device']['id']}", json={"status": "mantenimiento"})
    assert AutoIncidentService(db).run() == []


def test_anomalous_sensor_opens_report_only_over_threshold(db, client, station):  # noqa: F811
    threshold = get_settings().auto_incident_anomaly_threshold
    bad = [reading("hum", 140, "%") for _ in range(threshold - 1)]
    client.post(BATCH, json=batch(*bad), headers=headers(station))
    assert AutoIncidentService(db).run() == []

    client.post(BATCH, json=batch(reading("hum", 150, "%")), headers=headers(station))
    created = AutoIncidentService(db).run()

    assert [(r.auto_cause, r.sensor_id, r.priority) for r in created] == [
        ("lecturas_anomalas", station["sensors"]["hum"]["id"], "media")
    ]
    assert f"{threshold} lecturas" in created[0].description


def test_auto_report_follows_normal_flow_and_waits_before_reopening(db, station, people, travel):  # noqa: F811
    hours = get_settings().auto_incident_offline_hours
    silence(db, station, hours + 1)
    report_id = AutoIncidentService(db).run()[0].id

    listed = people["director"].get(INCIDENTS, params={"scope": "all"}).json()["items"]
    assert listed[0]["source"] == "sistema" and listed[0]["reporter"] is None
    tecnico = people["tecnico"]
    assert tecnico.post(f"{INCIDENTS}/{report_id}/accept").status_code == 200
    assert tecnico.post(f"{INCIDENTS}/{report_id}/start").status_code == 200
    finished = tecnico.post(f"{INCIDENTS}/{report_id}/finish", json=FINISH)
    assert finished.status_code == 200, finished.text

    # Recién finalizado: aunque siga sin datos, no se reabre dentro de la ventana.
    assert AutoIncidentService(db).run() == []
    # Pasada la ventana sin que la estación vuelva a comunicarse, se abre un reporte nuevo.
    travel(utcnow() + timedelta(hours=hours + 1))
    assert len(AutoIncidentService(db).run()) == 1
    assert len(auto_reports(db)) == 2
