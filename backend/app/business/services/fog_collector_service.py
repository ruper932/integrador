"""Vista integrada de cada atrapanieblas: ubicación, estado según sus estaciones IoT, captación,
tanque, reportes de incidencia y último mantenimiento."""

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.business.services.measurement_service import VOLUME_TYPE_CODE, MeasurementService
from app.core.clock import utcnow
from app.core.config import get_settings
from app.data.models.inventory import MAINTENANCE_FINISHED
from app.data.repositories.incidents import IncidentReportRepository
from app.data.repositories.inventory import MaintenanceRecordRepository
from app.data.repositories.iot import (
    DeviceRepository,
    FogCollectorRepository,
    SensorReadingRepository,
    SensorRepository,
    TankRepository,
)

TANK_LEVEL_CODE = "nivel_almacenamiento"


def fog_collector_status(*, is_active: bool, stations: Sequence[dict[str, Any]], incidents_in_attention: int) -> str:
    """Estado operativo derivado de las estaciones IoT asociadas (no se guarda: siempre está al día)."""
    if not is_active:
        return "inactivo"
    if not stations:
        return "sin_estacion"
    if incidents_in_attention or any(s["status"] == "mantenimiento" for s in stations):
        return "mantenimiento"
    if all(s["is_stale"] for s in stations if s["status"] == "activo"):
        return "sin_datos_recientes"
    return "operativo"


class FogCollectorOverviewService:
    def __init__(self, session: Session) -> None:
        self.fog_collectors = FogCollectorRepository(session)
        self.devices = DeviceRepository(session)
        self.sensors = SensorRepository(session)
        self.tanks = TankRepository(session)
        self.readings = SensorReadingRepository(session)
        self.incidents = IncidentReportRepository(session)
        self.maintenance = MaintenanceRecordRepository(session)
        self.measurements = MeasurementService(session)
        self.stale_after = timedelta(minutes=get_settings().device_stale_minutes)

    def overview(self) -> list[dict[str, Any]]:
        now = utcnow()
        latest = {r.sensor_id: r for r in self.readings.latest_valid_per_sensor()}
        return [self._one(fc, now, latest) for fc in self.fog_collectors.list(limit=1000, order_by=None)]

    def _one(self, fc: Any, now: datetime, latest: dict[int, Any]) -> dict[str, Any]:
        stations = [
            {
                "id": d.id,
                "code": d.code,
                "name": d.name,
                "status": d.status,
                "last_seen_at": d.last_seen_at,
                "is_stale": d.last_seen_at is None or now - d.last_seen_at > self.stale_after,
            }
            for d in self.devices.list(limit=100, fog_collector_id=fc.id)
        ]
        device_ids = [s["id"] for s in stations]

        open_incidents = []
        for device_id in device_ids:
            reports, _ = self.incidents.search(offset=0, limit=100, device_id=device_id)
            open_incidents += [
                {"id": r.id, "title": r.title, "status": r.status} for r in reports if r.status != "finalizado"
            ]
        last_maintenance: datetime | None = None
        for device_id in device_ids:
            records, _ = self.maintenance.search(offset=0, limit=1, device_id=device_id, status=MAINTENANCE_FINISHED)
            if records and (last_maintenance is None or records[0].performed_at > last_maintenance):
                last_maintenance = records[0].performed_at

        tanks = []
        for tank in self.tanks.list(limit=10, fog_collector_id=fc.id):
            level = next((latest[s.id] for s in self.sensors.list(limit=10, tank_id=tank.id) if s.id in latest), None)
            height = float(tank.height_cm) if tank.height_cm else None
            tanks.append(
                {
                    "code": tank.code,
                    "name": tank.name,
                    "capacity_liters": tank.capacity_liters,
                    "level_cm": level.value if level else None,
                    "level_at": level.measured_at if level else None,
                    "fill_share": min(level.value / height, 1.0) if level and height else None,
                }
            )

        series = self.measurements.series(
            sensor_type_code=VOLUME_TYPE_CODE,
            bucket="day",
            date_from=now - timedelta(days=7),
            date_to=now,
            fog_collector_id=fc.id,
        )
        daily = [{"date": p.bucket, "value": p.value} for p in series.points if p.value is not None]
        week = sum(p["value"] for p in daily)
        area = float(fc.mesh_area_m2) if fc.mesh_area_m2 else None
        location = fc.location
        return {
            "id": fc.id,
            "code": fc.code,
            "name": fc.name,
            "is_active": fc.is_active,
            "mesh_area_m2": fc.mesh_area_m2,
            "mesh_type": fc.mesh_type,
            "orientation": fc.orientation,
            "installed_on": fc.installed_on,
            "location": None
            if location is None
            else {
                "id": location.id,
                "name": location.name,
                "latitude": location.latitude,
                "longitude": location.longitude,
                "altitude_m": location.altitude_m,
            },
            "status": fog_collector_status(
                is_active=fc.is_active,
                stations=stations,
                incidents_in_attention=sum(1 for i in open_incidents if i["status"] != "abierto"),
            ),
            "stations": stations,
            "tanks": tanks,
            "volume_last_7_days": week,
            # Rendimiento de la malla: litros por m² y por día con datos.
            "liters_per_m2_day": week / len(daily) / area if area and daily else None,
            "daily": daily,
            "open_incidents": open_incidents,
            "last_maintenance_at": last_maintenance,
        }
