"""Carga de firmware y actualización OTA de las estaciones ESP32."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status

from app.business.rules.firmware import MAX_IMAGE_BYTES
from app.business.services.context import RequestContext
from app.business.services.firmware_service import FirmwareService
from app.core.errors import BusinessRuleError
from app.core.permissions import Permission
from app.presentation.api.deps import AuthContext, CurrentDevice, DbSession, client_ip, require
from app.presentation.schemas.firmware import (
    FirmwareAssignmentIn,
    FirmwareReleaseOut,
    FirstInstallIn,
    FirstInstallOut,
    FlashPartOut,
    StationDefaultsOut,
)
from app.presentation.schemas.iot import DeviceOut

router = APIRouter(tags=["Firmware"])

FirmwareManager = Annotated[AuthContext, Depends(require(Permission.FIRMWARE_MANAGE))]


async def firmware_image(request: Request) -> bytes:
    """Cuerpo binario de la solicitud, leído por partes y cortado si supera el tamaño máximo."""
    image = bytearray()
    async for chunk in request.stream():
        image.extend(chunk)
        if len(image) > MAX_IMAGE_BYTES:
            raise BusinessRuleError(
                f"El archivo supera el tamaño máximo de una ranura OTA ({MAX_IMAGE_BYTES} bytes).",
                code="firmware_muy_grande",
            )
    return bytes(image)


@router.get("/firmware/releases", response_model=list[FirmwareReleaseOut])
def list_releases(db: DbSession, _: FirmwareManager) -> list[FirmwareReleaseOut]:
    return [
        FirmwareReleaseOut(
            id=r.id,
            version=r.version,
            size_bytes=r.size_bytes,
            sha256=r.sha256,
            notes=r.notes,
            uploaded_by=r.uploaded_by.full_name,
            created_at=r.created_at,
            assigned_devices=count,
        )
        for r, count in FirmwareService(db).list_releases()
    ]


@router.post(
    "/firmware/releases",
    response_model=FirmwareReleaseOut,
    status_code=status.HTTP_201_CREATED,
    summary="Cargar un firmware.bin (cuerpo application/octet-stream); la versión se lee del archivo",
)
def upload_release(
    db: DbSession,
    auth: FirmwareManager,
    image: Annotated[bytes, Depends(firmware_image)],
    notes: Annotated[str | None, Query(max_length=500)] = None,
) -> FirmwareReleaseOut:
    release = FirmwareService(db).upload(auth.ctx, image, notes.strip() if notes and notes.strip() else None)
    return FirmwareReleaseOut(
        id=release.id,
        version=release.version,
        size_bytes=release.size_bytes,
        sha256=release.sha256,
        notes=release.notes,
        uploaded_by=auth.user.full_name,
        created_at=release.created_at,
        assigned_devices=0,
    )


@router.put("/firmware/assignments", response_model=list[DeviceOut], summary="Asignar una versión a estaciones")
def assign_release(payload: FirmwareAssignmentIn, db: DbSession, auth: FirmwareManager) -> list[DeviceOut]:
    devices = FirmwareService(db).assign(auth.ctx, payload.release_id, payload.device_ids)
    return [DeviceOut.model_validate(d) for d in devices]


@router.get(
    "/firmware/releases/{release_id}/flash-plan",
    response_model=list[FlashPartOut],
    summary="Primera instalación: imágenes a escribir por USB y su dirección en la memoria flash",
)
def flash_plan(release_id: int, db: DbSession, _: FirmwareManager) -> list[FlashPartOut]:
    return [FlashPartOut(**vars(p)) for p in FirmwareService(db).flash_plan(release_id)]


@router.get(
    "/firmware/releases/{release_id}/image",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}}}},
    summary="Imagen firmware.bin de una versión (para la primera instalación por USB)",
)
def release_image(release_id: int, db: DbSession, _: FirmwareManager) -> Response:
    return Response(content=FirmwareService(db).release(release_id).content, media_type="application/octet-stream")


@router.get(
    "/firmware/base/{name}",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}}}},
    summary="Imagen base de la primera instalación: bootloader, partitions o boot_app0",
)
def base_image(name: str, db: DbSession, _: FirmwareManager) -> Response:
    return Response(content=FirmwareService(db).base_image(name), media_type="application/octet-stream")


@router.post(
    "/firmware/first-install",
    response_model=FirstInstallOut,
    summary="Registrar la primera instalación: asigna la versión y emite una credencial nueva para el ESP32",
)
def first_install(payload: FirstInstallIn, db: DbSession, auth: FirmwareManager) -> FirstInstallOut:
    result = FirmwareService(db).first_install(auth.ctx, payload.device_id, payload.release_id)
    return FirstInstallOut(
        device_code=result.device.code,
        api_key=result.api_key,
        sample_interval_s=result.device.sample_interval_s,
        version=result.release.version,
        wifi_password=result.wifi_password,
    )


@router.get(
    "/firmware/station-defaults",
    response_model=StationDefaultsOut,
    summary="Datos de red que la primera instalación precarga (la contraseña Wi-Fi nunca se devuelve aquí)",
)
def station_defaults(_db: DbSession, _: FirmwareManager) -> StationDefaultsOut:
    return StationDefaultsOut(**vars(FirmwareService.station_defaults()))


@router.get(
    "/iot/firmware",
    summary="Actualización OTA para el ESP32: 200 con la imagen o 304 si no hay nada que instalar",
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}}}, 304: {"description": "Sin actualización"}},
)
def download_for_device(
    request: Request,
    db: DbSession,
    device: CurrentDevice,
    running_version: Annotated[str | None, Header(alias="x-ESP32-version", max_length=40)] = None,
) -> Response:
    ctx = RequestContext(user=None, ip=client_ip(request))
    release = FirmwareService(db).pending_for(ctx, device, running_version)
    if release is None:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED)
    # El cliente HTTPUpdate del ESP32 verifica el MD5 antes de dar por buena la imagen.
    return Response(content=release.content, media_type="application/octet-stream", headers={"x-MD5": release.md5})
