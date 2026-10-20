"""Dispositivos ESP32, sus credenciales y sensores."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.business.services.audit_service import AuditService
from app.business.services.context import RequestContext
from app.business.services.integrity import integrity_guard
from app.core.clock import utcnow
from app.core.errors import BusinessRuleError, ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import generate_device_key, keyed_hash
from app.data.models.iot import Device, DeviceCredential, DeviceLocation, Sensor
from app.data.repositories.iot import (
    DeviceCredentialRepository,
    DeviceLocationRepository,
    DeviceRepository,
    FogCollectorRepository,
    LocationRepository,
    SensorRepository,
    SensorTypeRepository,
    TankRepository,
)

logger = logging.getLogger(__name__)

VOLUME_SENSOR_CODE = "volumen_captado"
TANK_LEVEL_SENSOR_CODE = "nivel_almacenamiento"


@dataclass(frozen=True)
class DeviceWithKey:
    device: Device
    api_key: str


class DeviceAuthService:
    def __init__(self, session: Session) -> None:
        self.devices = DeviceRepository(session)
        self.credentials = DeviceCredentialRepository(session)

    def authenticate(self, device_code: str, api_key: str, *, ip: str | None) -> Device:
        device = self.devices.get_by_code(device_code)
        if device is None or self.credentials.get_active(device.id, keyed_hash(api_key)) is None:
            # Nunca se registra la credencial recibida.
            logger.warning("Autenticación de dispositivo fallida (id=%s, ip=%s)", device_code[:40], ip)
            raise UnauthorizedError("Credenciales de dispositivo inválidas.", code="dispositivo_no_autenticado")
        if device.status != "activo":
            raise ForbiddenError("El dispositivo no está activo.", code="dispositivo_inactivo")
        return device


class DeviceService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.devices = DeviceRepository(session)
        self.credentials = DeviceCredentialRepository(session)
        self.device_locations = DeviceLocationRepository(session)
        self.locations = LocationRepository(session)
        self.fog_collectors = FogCollectorRepository(session)
        self.audit = AuditService(session)

    def list(self, *, status: str | None = None) -> Sequence[Device]:
        return self.devices.list(limit=1000, status=status, order_by=Device.code)

    def get(self, device_id: int) -> Device:
        device = self.devices.get(device_id)
        if device is None:
            raise NotFoundError("Dispositivo no encontrado.")
        return device

    def current_location(self, device_id: int) -> DeviceLocation | None:
        return self.device_locations.get_current(device_id)

    def _issue_key(self, device: Device) -> str:
        api_key = generate_device_key()
        self.credentials.add(
            DeviceCredential(device_id=device.id, key_hash=keyed_hash(api_key), key_prefix=api_key[:8])
        )
        return api_key

    def _move_to(self, device: Device, location_id: int | None) -> None:
        current = self.device_locations.get_current(device.id)
        if current and current.location_id == location_id:
            return
        if location_id is not None and self.locations.get(location_id) is None:
            raise BusinessRuleError("La ubicación indicada no existe.", code="referencia_inexistente")
        now = utcnow()
        if current:
            current.ended_at = now
        if location_id is not None:
            self.device_locations.add(DeviceLocation(device_id=device.id, location_id=location_id, started_at=now))

    def create(self, ctx: RequestContext, data: dict[str, Any]) -> DeviceWithKey:
        location_id = data.pop("location_id", None)
        with integrity_guard(self.session, duplicate_message="Ya existe un dispositivo con ese identificador."):
            device = self.devices.add(Device(status="activo", **data))
        self._move_to(device, location_id)
        api_key = self._issue_key(device)
        self.audit.record(
            ctx, "dispositivo.crear", entity_type="device", entity_id=device.id, details={"code": device.code}
        )
        self.session.commit()
        return DeviceWithKey(device=device, api_key=api_key)

    def update(self, ctx: RequestContext, device_id: int, data: dict[str, Any]) -> Device:
        device = self.get(device_id)
        if "location_id" in data:
            self._move_to(device, data.pop("location_id"))
        with integrity_guard(self.session, duplicate_message="Ya existe un dispositivo con ese identificador."):
            for key, value in data.items():
                setattr(device, key, value)
        self.audit.record(
            ctx,
            "dispositivo.actualizar",
            entity_type="device",
            entity_id=device.id,
            details={k: str(v) for k, v in data.items()},
        )
        self.session.commit()
        return device

    def deactivate(self, ctx: RequestContext, device_id: int) -> Device:
        device = self.get(device_id)
        device.status = "inactivo"
        self.audit.record(ctx, "dispositivo.desactivar", entity_type="device", entity_id=device.id)
        self.session.commit()
        return device

    def rotate_key(self, ctx: RequestContext, device_id: int) -> DeviceWithKey:
        device = self.get(device_id)
        now = utcnow()
        for credential in self.credentials.list_active(device.id):
            credential.revoked_at = now
        api_key = self._issue_key(device)
        self.audit.record(ctx, "dispositivo.rotar_credencial", entity_type="device", entity_id=device.id)
        self.session.commit()
        return DeviceWithKey(device=device, api_key=api_key)


class SensorService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.sensors = SensorRepository(session)
        self.devices = DeviceRepository(session)
        self.sensor_types = SensorTypeRepository(session)
        self.fog_collectors = FogCollectorRepository(session)
        self.tanks = TankRepository(session)
        self.audit = AuditService(session)

    def list_types(self) -> Sequence[Any]:
        return self.sensor_types.list(limit=1000)

    def list(self, *, device_id: int | None = None, status: str | None = None) -> Sequence[Sensor]:
        return self.sensors.list(limit=5000, device_id=device_id, status=status)

    def get(self, sensor_id: int) -> Sensor:
        sensor = self.sensors.get(sensor_id)
        if sensor is None:
            raise NotFoundError("Sensor no encontrado.")
        return sensor

    def _validate_links(
        self, *, type_code: str, device: Device, fog_collector_id: int | None, tank_id: int | None
    ) -> None:
        if fog_collector_id is not None and self.fog_collectors.get(fog_collector_id) is None:
            raise BusinessRuleError("El atrapanieblas indicado no existe.", code="referencia_inexistente")
        if tank_id is not None and self.tanks.get(tank_id) is None:
            raise BusinessRuleError("El tanque indicado no existe.", code="referencia_inexistente")
        if type_code == VOLUME_SENSOR_CODE and fog_collector_id is None:
            raise BusinessRuleError(
                "Un sensor de volumen captado debe asociarse a un atrapanieblas.", code="atrapanieblas_requerido"
            )
        if type_code == TANK_LEVEL_SENSOR_CODE and tank_id is None:
            raise BusinessRuleError(
                "Un sensor de nivel de almacenamiento debe asociarse a un tanque.", code="tanque_requerido"
            )

    def create(self, ctx: RequestContext, data: dict[str, Any]) -> Sensor:
        device = self.devices.get(data["device_id"])
        if device is None:
            raise BusinessRuleError("El dispositivo indicado no existe.", code="referencia_inexistente")
        sensor_type = self.sensor_types.get(data["sensor_type_id"])
        if sensor_type is None:
            raise BusinessRuleError("El tipo de sensor indicado no existe.", code="referencia_inexistente")
        if data.get("fog_collector_id") is None and device.fog_collector_id is not None:
            data["fog_collector_id"] = device.fog_collector_id
        self._validate_links(
            type_code=sensor_type.code,
            device=device,
            fog_collector_id=data.get("fog_collector_id"),
            tank_id=data.get("tank_id"),
        )
        with integrity_guard(self.session, duplicate_message="El dispositivo ya tiene un sensor con ese código."):
            sensor = self.sensors.add(Sensor(status="activo", **data))
        self.audit.record(ctx, "sensor.crear", entity_type="sensor", entity_id=sensor.id, details={"code": sensor.code})
        self.session.commit()
        return sensor

    def update(self, ctx: RequestContext, sensor_id: int, data: dict[str, Any]) -> Sensor:
        sensor = self.get(sensor_id)
        self._validate_links(
            type_code=sensor.sensor_type.code,
            device=sensor.device,
            fog_collector_id=data.get("fog_collector_id", sensor.fog_collector_id),
            tank_id=data.get("tank_id", sensor.tank_id),
        )
        with integrity_guard(self.session, duplicate_message="El dispositivo ya tiene un sensor con ese código."):
            for key, value in data.items():
                setattr(sensor, key, value)
        self.audit.record(
            ctx,
            "sensor.actualizar",
            entity_type="sensor",
            entity_id=sensor.id,
            details={k: str(v) for k, v in data.items()},
        )
        self.session.commit()
        return sensor

    def deactivate(self, ctx: RequestContext, sensor_id: int) -> Sensor:
        sensor = self.get(sensor_id)
        sensor.status = "inactivo"
        self.audit.record(ctx, "sensor.desactivar", entity_type="sensor", entity_id=sensor.id)
        self.session.commit()
        return sensor
