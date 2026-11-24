"""Regla única de conexión: todos los módulos deben ver igual a una estación que dejó de comunicarse."""

from datetime import UTC, datetime, timedelta

from app.business.rules.connection import connection_state, stale_after
from app.core.clock import utcnow
from app.data.models.iot import Device
from tests.test_iot import BATCH, batch, headers, reading, station  # noqa: F401

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)


def test_rule_uses_the_sample_interval_with_the_configured_cap():
    assert stale_after(30) == timedelta(seconds=150)  # 3 intervalos + 60 s
    assert stale_after(5) == timedelta(seconds=75)
    assert stale_after(3600) == timedelta(minutes=30)  # nunca más que DEVICE_STALE_MINUTES
    assert stale_after(None) == timedelta(minutes=30)
    assert connection_state(None, 30, NOW) == "sin_comunicacion"
    assert connection_state(NOW - timedelta(seconds=140), 30, NOW) == "al_dia"
    assert connection_state(NOW - timedelta(seconds=160), 30, NOW) == "desactualizado"


def test_every_module_detects_the_lost_connection(admin_client, client, station, db):  # noqa: F811
    client.post(BATCH, json=batch(reading("temp", 10, "C")), headers=headers(station))
    device = db.get(Device, station["device"]["id"])
    device.sample_interval_s = 30
    device.last_seen_at = utcnow() - timedelta(minutes=3)  # antes, ningún módulo salvo monitoreo lo notaba
    db.commit()

    summary = admin_client.get("/api/v1/dashboard/summary").json()
    assert next(d for d in summary["devices"] if d["id"] == device.id)["is_stale"] is True
    live = admin_client.get("/api/v1/dashboard/live", params={"device_id": device.id, "minutes": 15}).json()
    assert live["device"]["is_stale"] is True
    lost = admin_client.get("/api/v1/devices", params={"connection": "desactualizado"}).json()
    assert [d["code"] for d in lost] == ["esp32-01"]
    overview = admin_client.get("/api/v1/fog-collectors/overview").json()
    assert all(s["is_stale"] for fc in overview for s in fc["stations"])

    client.post(BATCH, json=batch(reading("temp", 11, "C")), headers=headers(station))
    summary = admin_client.get("/api/v1/dashboard/summary").json()
    assert next(d for d in summary["devices"] if d["id"] == device.id)["is_stale"] is False
