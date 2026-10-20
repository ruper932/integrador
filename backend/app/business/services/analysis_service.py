"""Análisis estadístico: reúne en un periodo los indicadores pertinentes de cada módulo.

Cada sección solo se incluye si el usuario tiene el permiso de consulta de ese módulo.
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.business.rules.statistics import describe, pearson, strength
from app.business.services.context import RequestContext
from app.business.services.inventory_service import InventoryService
from app.business.services.maintenance_service import MaintenanceService
from app.business.services.measurement_service import VOLUME_TYPE_CODE, MeasurementService
from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.errors import BusinessRuleError
from app.core.permissions import Permission
from app.data.models.inventory import MAINTENANCE_FINISHED
from app.data.repositories.incidents import IncidentReportRepository
from app.data.repositories.iot import FogCollectorRepository, SensorReadingRepository, SensorTypeRepository

MAX_DAYS = 3 * 366
MAX_RECORDS = 50_000  # shortcut: agrega en memoria; si los registros crecen mucho, agregar en SQL.


def _hours(start: datetime | None, end: datetime | None) -> float | None:
    return (end - start).total_seconds() / 3600 if start and end else None


def _summary(values: list[float]) -> dict[str, Any]:
    return vars(describe(values))


class AnalysisService:
    def __init__(self, session: Session) -> None:
        self.measurements = MeasurementService(session)
        self.sensor_types = SensorTypeRepository(session)
        self.fog_collectors = FogCollectorRepository(session)
        self.readings = SensorReadingRepository(session)
        self.maintenance = MaintenanceService(session)
        self.incidents = IncidentReportRepository(session)
        self.inventory = InventoryService(session)
        self.tz = ZoneInfo(get_settings().local_timezone)

    def analyze(
        self,
        ctx: RequestContext,
        *,
        date_from: datetime | None,
        date_to: datetime | None,
        device_id: int | None = None,
        fog_collector_id: int | None = None,
    ) -> dict[str, Any]:
        date_to = date_to or utcnow()
        date_from = date_from or date_to - timedelta(days=30)
        if date_from >= date_to:
            raise BusinessRuleError("La fecha inicial debe ser anterior a la final.", code="rango_invalido")
        if date_to - date_from > timedelta(days=MAX_DAYS):
            raise BusinessRuleError("El periodo de análisis no puede superar tres años.", code="rango_muy_amplio")
        codes = ctx.user.permission_codes if ctx.user else set()
        scope = {"date_from": date_from, "date_to": date_to}
        place = {"device_id": device_id, "fog_collector_id": fog_collector_id}
        result: dict[str, Any] = {"date_from": date_from, "date_to": date_to}
        if Permission.MEASUREMENTS_READ.value in codes:
            result |= self._monitoring(scope, place)
        if Permission.MAINTENANCE_READ.value in codes:
            result["maintenance"] = self._maintenance(scope, device_id)
        if Permission.INCIDENTS_SUPERVISE.value in codes:
            result["incidents"] = self._incidents(scope, device_id)
        if Permission.INVENTORY_READ.value in codes:
            result["inventory"] = self._inventory(scope, device_id)
        return result

    # --- Monitoreo ----------------------------------------------------------------

    def _daily(self, type_code: str, scope: dict[str, Any], place: dict[str, Any]) -> dict[str, float]:
        series = self.measurements.series(sensor_type_code=type_code, bucket="day", **scope, **place)
        return {p.bucket.astimezone(self.tz).date().isoformat(): p.value for p in series.points if p.value is not None}

    def _monitoring(self, scope: dict[str, Any], place: dict[str, Any]) -> dict[str, Any]:
        volume = self._daily(VOLUME_TYPE_CODE, scope, place)
        days = sorted(volume)
        values = [volume[d] for d in days]
        by_fog = []
        if place["fog_collector_id"] is None:
            for fog in self.fog_collectors.list(limit=100):
                total = sum(self._daily(VOLUME_TYPE_CODE, scope, {**place, "fog_collector_id": fog.id}).values())
                by_fog.append({"name": fog.name, "total": total})
        grand = sum(values)
        for row in by_fog:
            row["share"] = row["total"] / grand if grand else None
        capture = {
            "total": grand,
            "days_with_data": len(days),
            "days_with_capture": sum(1 for v in values if v > 0),
            "daily": _summary(values),
            "best_day": max(volume.items(), key=lambda kv: kv[1], default=(None, None))[0],
            "series": [{"date": d, "value": volume[d]} for d in days],
            "by_fog_collector": by_fog,
        }

        variables, correlations = [], []
        for sensor_type in self.sensor_types.list(limit=100):
            if sensor_type.aggregation != "instantaneo":
                continue
            daily = self._daily(sensor_type.code, scope, place)
            summary = _summary(list(daily.values()))
            variables.append({"code": sensor_type.code, "name": sensor_type.name, "unit": sensor_type.unit, **summary})
            paired = [d for d in days if d in daily]
            r = pearson([daily[d] for d in paired], [volume[d] for d in paired])
            correlations.append(
                {
                    "code": sensor_type.code,
                    "name": sensor_type.name,
                    "unit": sensor_type.unit,
                    "r": r,
                    "n": len(paired),
                    "strength": strength(r),
                    # Pares diarios (variable, volumen) para el diagrama de dispersión.
                    "points": [{"date": d, "x": daily[d], "y": volume[d]} for d in paired],
                }
            )

        counts = self.readings.count_by_device_and_quality(
            date_from=scope["date_from"], date_to=scope["date_to"], **place
        )
        by_quality: Counter[str] = Counter()
        per_device: dict[str, Counter[str]] = defaultdict(Counter)
        for device, quality, count in counts:
            by_quality[quality] += count
            per_device[device][quality] += count
        total = sum(by_quality.values())
        quality = {
            "total": total,
            "by_quality": dict(by_quality),
            "valid_share": by_quality["valida"] / total if total else None,
            "by_device": [
                {"device": d, "total": sum(c.values()), "valid_share": c["valida"] / sum(c.values())}
                for d, c in per_device.items()
            ],
        }
        return {"capture": capture, "variables": variables, "correlations": correlations, "quality": quality}

    # --- Mantenimiento, incidencias e inventario ----------------------------------

    def _maintenance(self, scope: dict[str, Any], device_id: int | None) -> dict[str, Any]:
        records, _ = self.maintenance.search(
            offset=0, limit=MAX_RECORDS, device_id=device_id, status=MAINTENANCE_FINISHED, **scope
        )
        return {
            "total": len(records),
            "by_type": dict(Counter(r.maintenance_type for r in records)),
            "by_final_status": dict(Counter(r.final_status for r in records)),
            "from_incidents": sum(1 for r in records if r.incident_report_id),
            "with_parts": sum(1 for r in records if r.items),
        }

    def _incidents(self, scope: dict[str, Any], device_id: int | None) -> dict[str, Any]:
        reports, _ = self.incidents.search(offset=0, limit=MAX_RECORDS, device_id=device_id, **scope)
        attended = [r for r in reports if r.maintenance]
        to_accept = [h for r in attended if (h := _hours(r.created_at, r.maintenance.accepted_at)) is not None]  # type: ignore[union-attr]
        to_finish = [h for r in attended if (h := _hours(r.created_at, r.maintenance.finished_at)) is not None]  # type: ignore[union-attr]
        return {
            "total": len(reports),
            "by_status": dict(Counter(r.status for r in reports)),
            "by_priority": dict(Counter(r.priority for r in reports)),
            "hours_to_accept": _summary(to_accept),
            "hours_to_finish": _summary(to_finish),
        }

    def _inventory(self, scope: dict[str, Any], device_id: int | None) -> dict[str, Any]:
        records, _ = self.maintenance.search(
            offset=0, limit=MAX_RECORDS, device_id=device_id, status=MAINTENANCE_FINISHED, **scope
        )
        used: dict[str, dict[str, Any]] = {}
        for record in records:
            for part in record.items:
                row = used.setdefault(
                    part.item.code,
                    {"code": part.item.code, "name": part.item.name, "unit": part.item.unit, "quantity": Decimal(0)},
                )
                row["quantity"] += part.quantity
        return {
            "low_stock": len(self.inventory.stock_report(include_inactive=False, low_stock_only=True)),
            "top_consumed": sorted(used.values(), key=lambda r: r["quantity"], reverse=True)[:10],
        }
