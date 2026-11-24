"""Carga de firmware y actualización OTA de las estaciones ESP32."""

import hashlib

import pytest
from sqlalchemy import select

from app.business.rules.firmware import MAX_IMAGE_BYTES, firmware_version
from app.core.errors import BusinessRuleError
from app.data.models.security import AuditLog
from tests.test_iot import headers, station  # noqa: F401

RELEASES = "/api/v1/firmware/releases"
ASSIGN = "/api/v1/firmware/assignments"
OTA = "/api/v1/iot/firmware"
BINARY = {"Content-Type": "application/octet-stream"}


def image(version: str | None = "0.2.0", *, magic: int = 0xE9, chip: int = 0, size: int = 4096) -> bytes:
    """Imagen mínima con la cabecera de una aplicación ESP32 y la marca de versión del firmware ATINA."""
    header = bytes([magic, 3, 2, 0x20]) + bytes(8) + chip.to_bytes(2, "little") + bytes(10)
    body = header + (f"ATINA-FW:{version};".encode() if version else b"")
    return body + bytes(size - len(body))


def test_image_rules():
    assert firmware_version(image("0.2.0")) == "0.2.0"
    cases = [
        (image(magic=0x00), "firmware_invalido"),
        (b"\xe9" * 10, "firmware_invalido"),
        (image(chip=9), "firmware_chip"),  # p. ej. un binario de ESP32-S3
        (image(None), "firmware_sin_version"),
        (image("0.2.0") + b"ATINA-FW:0.3.0;", "firmware_sin_version"),  # dos versiones distintas
        (image(size=MAX_IMAGE_BYTES + 1), "firmware_muy_grande"),
    ]
    for data, code in cases:
        with pytest.raises(BusinessRuleError) as error:
            firmware_version(data)
        assert error.value.code == code


def test_upload_assign_and_ota_download(admin_client, client, station, db):  # noqa: F811
    data = image("0.2.0")
    uploaded = admin_client.post(RELEASES, content=data, headers=BINARY, params={"notes": "DHT11 + BME280"})
    assert uploaded.status_code == 201, uploaded.text
    release = uploaded.json()
    assert release["version"] == "0.2.0"
    assert release["sha256"] == hashlib.sha256(data).hexdigest()
    assert release["notes"] == "DHT11 + BME280"
    duplicate = admin_client.post(RELEASES, content=data, headers=BINARY)
    assert duplicate.json()["error"]["code"] == "firmware_duplicado"

    # Sin versión asignada, la estación no descarga nada.
    assert client.get(OTA, headers={**headers(station), "x-ESP32-version": "0.1.0"}).status_code == 304

    assigned = admin_client.put(ASSIGN, json={"release_id": release["id"], "device_ids": [station["device"]["id"]]})
    assert assigned.json()[0]["target_firmware_version"] == "0.2.0"
    devices = admin_client.get("/api/v1/devices").json()
    assert next(d for d in devices if d["id"] == station["device"]["id"])["target_firmware_version"] == "0.2.0"
    assert admin_client.get(RELEASES).json()[0]["assigned_devices"] == 1

    download = client.get(OTA, headers={**headers(station), "x-ESP32-version": "0.1.0"})
    assert download.status_code == 200
    assert download.content == data
    assert download.headers["x-MD5"] == hashlib.md5(data, usedforsecurity=False).hexdigest()  # lo verifica el ESP32
    # Ya ejecuta la versión asignada: no vuelve a descargarla (sin bucle de actualizaciones).
    assert client.get(OTA, headers={**headers(station), "x-ESP32-version": "0.2.0"}).status_code == 304
    assert client.get(OTA).status_code == 401

    admin_client.put(ASSIGN, json={"release_id": None, "device_ids": [station["device"]["id"]]})
    assert client.get(OTA, headers={**headers(station), "x-ESP32-version": "0.1.0"}).status_code == 304

    actions = set(db.scalars(select(AuditLog.action).where(AuditLog.action.startswith("firmware."))))
    assert actions == {"firmware.cargar", "firmware.asignar", "firmware.descargar"}


def test_only_admin_and_maintenance_manage_firmware(make_client, factory):
    technician = factory.client_for(make_client(), "tec-fw", ["mantenimiento"])
    assert technician.post(RELEASES, content=image("0.3.0"), headers=BINARY).status_code == 201
    assert technician.get(RELEASES).status_code == 200
    for role in ("docente", "director"):
        other = factory.client_for(make_client(), f"{role}-fw", [role])
        assert other.get(RELEASES).status_code == 403
        assert other.post(RELEASES, content=image("0.4.0"), headers=BINARY).status_code == 403


def test_upload_rejects_invalid_files(admin_client):
    too_big = admin_client.post(RELEASES, content=image(size=MAX_IMAGE_BYTES + 10), headers=BINARY)
    assert too_big.json()["error"]["code"] == "firmware_muy_grande"
    not_esp32 = admin_client.post(RELEASES, content=b"%PDF-1.7 no es firmware", headers=BINARY)
    assert not_esp32.json()["error"]["code"] == "firmware_invalido"
    assert admin_client.get(RELEASES).json() == []


def test_first_install_plan_images_and_new_credential(admin_client, client, station, db):  # noqa: F811
    data = image("0.5.0")
    release = admin_client.post(RELEASES, content=data, headers=BINARY).json()

    plan = admin_client.get(f"{RELEASES}/{release['id']}/flash-plan").json()
    assert [(p["name"], p["address"]) for p in plan] == [
        ("bootloader", 0x1000),
        ("partitions", 0x8000),
        ("boot_app0", 0xE000),
        ("firmware", 0x10000),
    ]
    for part in plan[:3]:
        body = admin_client.get(f"/api/v1/firmware/base/{part['name']}").content
        assert hashlib.sha256(body).hexdigest() == part["sha256"]
    assert admin_client.get(f"{RELEASES}/{release['id']}/image").content == data
    assert admin_client.get("/api/v1/firmware/base/../../.env").status_code == 404

    device_id = station["device"]["id"]
    done = admin_client.post(
        "/api/v1/firmware/first-install", json={"device_id": device_id, "release_id": release["id"]}
    )
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["device_code"] == "esp32-01" and body["version"] == "0.5.0"
    # La credencial anterior queda revocada y la nueva funciona.
    assert client.get(OTA, headers=headers(station)).status_code == 401
    fresh = {"X-Device-Id": "esp32-01", "X-Device-Key": body["api_key"], "x-ESP32-version": "0.5.0"}
    assert client.get(OTA, headers=fresh).status_code == 304  # ya ejecuta la versión asignada
    actions = set(db.scalars(select(AuditLog.action)))
    assert {"firmware.primera_instalacion", "dispositivo.rotar_credencial"} <= actions
    assert body["api_key"] not in str(list(db.scalars(select(AuditLog.details))))


def test_first_install_requires_firmware_permission_and_active_device(admin_client, make_client, factory, station):  # noqa: F811
    release = admin_client.post(RELEASES, content=image("0.6.0"), headers=BINARY).json()
    director = factory.client_for(make_client(), "dir-fi", ["director"])
    payload = {"device_id": station["device"]["id"], "release_id": release["id"]}
    assert director.post("/api/v1/firmware/first-install", json=payload).status_code == 403
    assert director.get("/api/v1/firmware/base/bootloader").status_code == 403
    admin_client.put(f"/api/v1/devices/{station['device']['id']}", json={"status": "inactivo"})
    refused = admin_client.post("/api/v1/firmware/first-install", json=payload)
    assert refused.json()["error"]["code"] == "dispositivo_inactivo"


def test_station_defaults_never_expose_the_wifi_password(admin_client, station, monkeypatch):  # noqa: F811
    from pydantic import SecretStr

    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "station_wifi_ssid", "LAB")
    monkeypatch.setattr(settings, "station_wifi_password", SecretStr("clave-wifi"))
    monkeypatch.setattr(settings, "station_api_url", "http://10.0.0.5:8000/api/v1/iot/measurements/batch")
    monkeypatch.setattr(settings, "station_ntp_server", "10.0.0.5")

    defaults = admin_client.get("/api/v1/firmware/station-defaults")
    assert defaults.json() == {
        "wifi_ssid": "LAB",
        "wifi_password_saved": True,
        "api_url": "http://10.0.0.5:8000/api/v1/iot/measurements/batch",
        "ntp_server": "10.0.0.5",
    }
    assert "clave-wifi" not in defaults.text
    release = admin_client.post(RELEASES, content=image("0.7.0"), headers=BINARY).json()
    payload = {"device_id": station["device"]["id"], "release_id": release["id"]}
    assert admin_client.post("/api/v1/firmware/first-install", json=payload).json()["wifi_password"] == "clave-wifi"
