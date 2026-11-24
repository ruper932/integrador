"""Carga de firmware y actualización OTA de las estaciones ESP32 por la red local.

Flujo: el administrador o el técnico de mantenimiento carga el `firmware.bin` → lo asigna a una o
varias estaciones → cada estación consulta periódicamente `GET /api/v1/iot/firmware`; si la versión
asignada difiere de la que ejecuta, la descarga, verifica el MD5 e instala. El servidor no "empuja"
nada: el ESP32 la pide con su propia credencial.
"""

import hashlib
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.business.rules.firmware import firmware_version
from app.business.services.audit_service import AuditService
from app.business.services.context import RequestContext
from app.business.services.device_service import DeviceService
from app.core.config import get_settings
from app.core.errors import BusinessRuleError, ConflictError, NotFoundError
from app.data.models.iot import Device, FirmwareRelease
from app.data.repositories.iot import DeviceRepository, FirmwareReleaseRepository

# Imágenes de la primera instalación y su dirección en la memoria flash del ESP32 (placa esp32dev).
BASE_PARTS: dict[str, int] = {"bootloader": 0x1000, "partitions": 0x8000, "boot_app0": 0xE000}
APP_ADDRESS = 0x10000


@dataclass(frozen=True)
class FlashPart:
    name: str
    address: int
    size: int
    sha256: str


@dataclass(frozen=True)
class FirstInstall:
    device: Device
    api_key: str
    release: FirmwareRelease
    wifi_password: str | None  # la guardada en el servidor, para enviarla al ESP32 sin mostrarla


@dataclass(frozen=True)
class StationDefaults:
    wifi_ssid: str
    wifi_password_saved: bool
    api_url: str
    ntp_server: str


class FirmwareService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.releases = FirmwareReleaseRepository(session)
        self.devices = DeviceRepository(session)
        self.audit = AuditService(session)

    def list_releases(self) -> list[tuple[FirmwareRelease, int]]:
        """Versiones cargadas (la más reciente primero) con la cantidad de estaciones que la tienen asignada."""
        assigned = Counter(d.target_firmware_id for d in self.devices.list(limit=10_000) if d.target_firmware_id)
        releases = self.releases.list(limit=1000, order_by=FirmwareRelease.id.desc())
        return [(r, assigned[r.id]) for r in releases]

    def upload(self, ctx: RequestContext, image: bytes, notes: str | None) -> FirmwareRelease:
        version = firmware_version(image)
        if self.releases.get_by(version=version):
            raise ConflictError(
                f"La versión {version} ya está cargada. Cambie FIRMWARE_VERSION y vuelva a compilar.",
                code="firmware_duplicado",
            )
        release = self.releases.add(
            FirmwareRelease(
                version=version,
                size_bytes=len(image),
                sha256=hashlib.sha256(image).hexdigest(),
                md5=hashlib.md5(image, usedforsecurity=False).hexdigest(),
                content=image,
                notes=notes,
                uploaded_by_id=ctx.user_id,
            )
        )
        self.audit.record(
            ctx,
            "firmware.cargar",
            entity_type="firmware_release",
            entity_id=release.id,
            details={"version": version, "bytes": len(image), "sha256": release.sha256},
        )
        self.session.commit()
        return release

    def assign(self, ctx: RequestContext, release_id: int | None, device_ids: Sequence[int]) -> list[Device]:
        """Asigna una versión (o ninguna) a las estaciones. Asignar una versión anterior es un retroceso válido."""
        release = None
        if release_id is not None:
            release = self.releases.get(release_id)
            if release is None:
                raise NotFoundError("Versión de firmware no encontrada.")
        devices = []
        for device_id in dict.fromkeys(device_ids):
            device = self.devices.get(device_id)
            if device is None:
                raise NotFoundError(f"Dispositivo {device_id} no encontrado.")
            device.target_firmware = release
            devices.append(device)
        self.audit.record(
            ctx,
            "firmware.asignar",
            entity_type="firmware_release",
            entity_id=release_id,
            details={"version": release.version if release else None, "dispositivos": [d.code for d in devices]},
        )
        self.session.commit()
        return devices

    def pending_for(self, ctx: RequestContext, device: Device, running_version: str | None) -> FirmwareRelease | None:
        """Imagen que la estación debe instalar, o None si ya ejecuta la asignada (o no hay asignación)."""
        release = device.target_firmware
        current = running_version or device.firmware_version
        if release is None or release.version == current:
            return None
        self.audit.record(
            ctx,
            "firmware.descargar",
            entity_type="device",
            entity_id=device.id,
            details={"dispositivo": device.code, "desde": current, "hacia": release.version},
        )
        self.session.commit()
        return release

    # --- Primera instalación por USB (desde el navegador) ---------------------------------

    def release(self, release_id: int) -> FirmwareRelease:
        release = self.releases.get(release_id)
        if release is None:
            raise NotFoundError("Versión de firmware no encontrada.")
        return release

    def base_image(self, name: str) -> bytes:
        if name not in BASE_PARTS:
            raise NotFoundError("Imagen base no encontrada.")
        path = get_settings().firmware_base_dir / f"{name}.bin"
        if not path.is_file():
            raise BusinessRuleError(
                "Faltan las imágenes base de la primera instalación en el servidor (ver backend/firmware_base).",
                code="imagen_base_faltante",
            )
        return path.read_bytes()

    @staticmethod
    def station_defaults() -> StationDefaults:
        """Datos de red que la primera instalación precarga (configurados en el servidor)."""
        settings = get_settings()
        return StationDefaults(
            wifi_ssid=settings.station_wifi_ssid,
            wifi_password_saved=bool(settings.station_wifi_password.get_secret_value()),
            api_url=settings.station_api_url,
            ntp_server=settings.station_ntp_server,
        )

    def flash_plan(self, release_id: int) -> list[FlashPart]:
        """Qué se escribe y dónde: bootloader, particiones, boot_app0 y el firmware elegido."""
        release = self.release(release_id)
        parts = [
            FlashPart(name, address, len(data), hashlib.sha256(data).hexdigest())
            for name, address in BASE_PARTS.items()
            for data in [self.base_image(name)]
        ]
        return [*parts, FlashPart("firmware", APP_ADDRESS, release.size_bytes, release.sha256)]

    def first_install(self, ctx: RequestContext, device_id: int, release_id: int) -> FirstInstall:
        """Tras escribir la imagen por USB: nueva credencial para cargarla en el ESP32 y versión asignada.

        La credencial anterior queda revocada; la nueva no se muestra en pantalla, el navegador la envía
        directo al ESP32 por el puerto serie.
        """
        release = self.release(release_id)
        device = self.devices.get(device_id)
        if device is None:
            raise NotFoundError("Dispositivo no encontrado.")
        if device.status == "inactivo":
            raise BusinessRuleError(
                "El dispositivo está desactivado: actívelo antes de instalarle el firmware.",
                code="dispositivo_inactivo",
            )
        # Así la actualización por red no vuelve a instalar la misma versión.
        device.target_firmware = release
        self.audit.record(
            ctx,
            "firmware.primera_instalacion",
            entity_type="device",
            entity_id=device.id,
            details={"dispositivo": device.code, "version": release.version},
        )
        with_key = DeviceService(self.session).rotate_key(ctx, device.id)  # registra su auditoría y confirma
        saved = get_settings().station_wifi_password.get_secret_value()
        return FirstInstall(device=device, api_key=with_key.api_key, release=release, wifi_password=saved or None)
