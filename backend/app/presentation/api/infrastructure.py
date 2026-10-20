"""Endpoints de infraestructura física, dispositivos y sensores."""

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.business.services.device_service import DeviceService, SensorService
from app.business.services.fog_collector_service import FogCollectorOverviewService
from app.business.services.infrastructure_service import (
    CatalogService,
    fog_collector_service,
    greenhouse_service,
    location_service,
    tank_service,
)
from app.core.permissions import Permission
from app.presentation.api.deps import AuthContext, DbSession, require
from app.presentation.schemas.iot import (
    DeviceIn,
    DeviceOut,
    DeviceStatus,
    DeviceUpdate,
    DeviceWithKeyOut,
    FogCollectorIn,
    FogCollectorOut,
    FogCollectorUpdate,
    GreenhouseIn,
    GreenhouseOut,
    GreenhouseUpdate,
    LocationIn,
    LocationOut,
    LocationUpdate,
    SensorIn,
    SensorOut,
    SensorTypeOut,
    SensorUpdate,
    TankIn,
    TankOut,
    TankUpdate,
)

router = APIRouter(tags=["Infraestructura y dispositivos"])

Reader = Annotated[AuthContext, Depends(require(Permission.INFRASTRUCTURE_READ))]
Manager = Annotated[AuthContext, Depends(require(Permission.INFRASTRUCTURE_MANAGE))]


def _register_catalog(
    path: str,
    factory: Callable[[Session], CatalogService],
    schema_in: type[BaseModel],
    schema_update: type[BaseModel],
    schema_out: type[BaseModel],
    label: str,
) -> None:
    """Registra listar/crear/consultar/actualizar/desactivar para una entidad de infraestructura."""

    def list_entities(db: DbSession, _: Reader, include_inactive: bool = False) -> list[Any]:
        return [schema_out.model_validate(e) for e in factory(db).list(include_inactive=include_inactive)]

    def create_entity(payload: schema_in, db: DbSession, auth: Manager) -> Any:  # type: ignore[valid-type]
        return schema_out.model_validate(factory(db).create(auth.ctx, payload.model_dump()))  # type: ignore[attr-defined]

    def get_entity(entity_id: int, db: DbSession, _: Reader) -> Any:
        return schema_out.model_validate(factory(db).get(entity_id))

    def update_entity(entity_id: int, payload: schema_update, db: DbSession, auth: Manager) -> Any:  # type: ignore[valid-type]
        data = payload.model_dump(exclude_unset=True)  # type: ignore[attr-defined]
        return schema_out.model_validate(factory(db).update(auth.ctx, entity_id, data))

    def deactivate_entity(entity_id: int, db: DbSession, auth: Manager) -> Any:
        return schema_out.model_validate(factory(db).deactivate(auth.ctx, entity_id))

    router.add_api_route(
        path, list_entities, methods=["GET"], response_model=list[schema_out], summary=f"Listar {label}"
    )
    router.add_api_route(
        path,
        create_entity,
        methods=["POST"],
        response_model=schema_out,
        status_code=status.HTTP_201_CREATED,
        summary=f"Crear {label}",
    )
    router.add_api_route(f"{path}/{{entity_id}}", get_entity, methods=["GET"], response_model=schema_out)
    router.add_api_route(f"{path}/{{entity_id}}", update_entity, methods=["PUT"], response_model=schema_out)
    router.add_api_route(
        f"{path}/{{entity_id}}",
        deactivate_entity,
        methods=["DELETE"],
        response_model=schema_out,
        summary=f"Desactivar {label} (no se elimina)",
    )


# Se registra antes que «/fog-collectors/{entity_id}» para que «overview» no se lea como identificador.
@router.get(
    "/fog-collectors/overview",
    summary="Atrapanieblas con ubicación, estado según sus estaciones IoT, captación y mantenimiento",
)
def fog_collectors_overview(db: DbSession, _: Reader) -> list[dict[str, Any]]:
    # shortcut: respuesta sin esquema Pydantic propio; tiparla si otro cliente la consume.
    return FogCollectorOverviewService(db).overview()


_register_catalog("/locations", location_service, LocationIn, LocationUpdate, LocationOut, "ubicaciones")
_register_catalog(
    "/fog-collectors", fog_collector_service, FogCollectorIn, FogCollectorUpdate, FogCollectorOut, "atrapanieblas"
)
_register_catalog("/tanks", tank_service, TankIn, TankUpdate, TankOut, "tanques")
_register_catalog("/greenhouses", greenhouse_service, GreenhouseIn, GreenhouseUpdate, GreenhouseOut, "invernaderos")


# --- Dispositivos ----------------------------------------------------------


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(
    db: DbSession, _: Reader, status: DeviceStatus | None = None, fog_collector_id: int | None = None
) -> list[DeviceOut]:
    devices = DeviceService(db).list(status=status, fog_collector_id=fog_collector_id)
    return [DeviceOut.model_validate(d) for d in devices]


@router.post("/devices", response_model=DeviceWithKeyOut, status_code=status.HTTP_201_CREATED)
def create_device(payload: DeviceIn, db: DbSession, auth: Manager) -> DeviceWithKeyOut:
    result = DeviceService(db).create(auth.ctx, payload.model_dump())
    return DeviceWithKeyOut(device=DeviceOut.model_validate(result.device), api_key=result.api_key)


@router.get("/devices/{device_id}", response_model=DeviceOut)
def get_device(device_id: int, db: DbSession, _: Reader) -> DeviceOut:
    return DeviceOut.model_validate(DeviceService(db).get(device_id))


@router.put("/devices/{device_id}", response_model=DeviceOut)
def update_device(device_id: int, payload: DeviceUpdate, db: DbSession, auth: Manager) -> DeviceOut:
    return DeviceOut.model_validate(
        DeviceService(db).update(auth.ctx, device_id, payload.model_dump(exclude_unset=True))
    )


@router.delete("/devices/{device_id}", response_model=DeviceOut, summary="Desactivar dispositivo (no se elimina)")
def deactivate_device(device_id: int, db: DbSession, auth: Manager) -> DeviceOut:
    return DeviceOut.model_validate(DeviceService(db).deactivate(auth.ctx, device_id))


@router.post(
    "/devices/{device_id}/credentials", response_model=DeviceWithKeyOut, summary="Rotar API key del dispositivo"
)
def rotate_device_key(device_id: int, db: DbSession, auth: Manager) -> DeviceWithKeyOut:
    result = DeviceService(db).rotate_key(auth.ctx, device_id)
    return DeviceWithKeyOut(device=DeviceOut.model_validate(result.device), api_key=result.api_key)


# --- Sensores --------------------------------------------------------------


@router.get("/sensor-types", response_model=list[SensorTypeOut])
def list_sensor_types(db: DbSession, _: Reader) -> list[SensorTypeOut]:
    return [SensorTypeOut.model_validate(t) for t in SensorService(db).list_types()]


@router.get("/sensors", response_model=list[SensorOut])
def list_sensors(
    db: DbSession, _: Reader, device_id: int | None = None, status: DeviceStatus | None = None
) -> list[SensorOut]:
    return [SensorOut.model_validate(s) for s in SensorService(db).list(device_id=device_id, status=status)]


@router.post("/sensors", response_model=SensorOut, status_code=status.HTTP_201_CREATED)
def create_sensor(payload: SensorIn, db: DbSession, auth: Manager) -> SensorOut:
    return SensorOut.model_validate(SensorService(db).create(auth.ctx, payload.model_dump()))


@router.get("/sensors/{sensor_id}", response_model=SensorOut)
def get_sensor(sensor_id: int, db: DbSession, _: Reader) -> SensorOut:
    return SensorOut.model_validate(SensorService(db).get(sensor_id))


@router.put("/sensors/{sensor_id}", response_model=SensorOut)
def update_sensor(sensor_id: int, payload: SensorUpdate, db: DbSession, auth: Manager) -> SensorOut:
    return SensorOut.model_validate(
        SensorService(db).update(auth.ctx, sensor_id, payload.model_dump(exclude_unset=True))
    )


@router.delete("/sensors/{sensor_id}", response_model=SensorOut, summary="Desactivar sensor (no se elimina)")
def deactivate_sensor(sensor_id: int, db: DbSession, auth: Manager) -> SensorOut:
    return SensorOut.model_validate(SensorService(db).deactivate(auth.ctx, sensor_id))
