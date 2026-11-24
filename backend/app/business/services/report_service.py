"""Construcción de reportes a partir de los datos del sistema.

Qué reportes existen, qué permiso exigen y qué filtros admiten se define en `report_catalog`.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.business.rules.connection import CONNECTION_LABELS, MISSED_INTERVALS, connection_state
from app.business.services.analysis_service import AnalysisService
from app.business.services.audit_service import AuditService
from app.business.services.context import RequestContext
from app.business.services.device_service import DeviceService
from app.business.services.inventory_period_service import InventoryPeriodService, PeriodSummary
from app.business.services.inventory_service import InventoryService
from app.business.services.maintenance_service import MaintenanceService
from app.business.services.measurement_service import VOLUME_TYPE_CODE, MeasurementService
from app.business.services.report_catalog import (
    BY_KIND,
    FILTER_LABELS,
    REQUIRED_ERROR_CODES,
    ReportDefinition,
    available_for,
)
from app.business.services.report_charts import add_charts, readable
from app.business.services.report_renderers import RENDERERS, Chart, RenderedFile, Report, Series
from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.errors import BusinessRuleError, ForbiddenError
from app.core.permissions import Permission
from app.data.models.inventory import MAINTENANCE_FINISHED
from app.data.models.security import User
from app.data.repositories.incidents import IncidentReportRepository
from app.data.repositories.inventory import (
    InventoryCategoryRepository,
    InventoryItemRepository,
    InventoryMovementRepository,
    InventoryMovementTypeRepository,
    InventoryPeriodRepository,
)
from app.data.repositories.iot import (
    DeviceRepository,
    FogCollectorRepository,
    SensorRepository,
    SensorTypeRepository,
)
from app.data.repositories.people import PositionRepository
from app.data.repositories.security import AuditLogRepository, RoleRepository, UserRepository

MAX_REPORT_ROWS = 50_000
BUCKET_LABELS = {"hour": "hora", "day": "día", "week": "semana", "month": "mes"}
ORIGIN_LABELS = {"incidencia": "Atención de reportes de incidencia", "directo": "Registro directo"}
# Filtros que el propio reporte ya describe en su encabezado.
SELF_DESCRIBED = {"date_range", "period_id"}


@dataclass(frozen=True)
class ReportFilters:
    date_from: datetime | None = None
    date_to: datetime | None = None
    bucket: str = "day"
    # Monitoreo
    device_id: int | None = None
    sensor_type: str | None = None
    fog_collector_id: int | None = None
    quality: str | None = None
    device_status: str | None = None
    connection: str | None = None
    # Inventario
    category_id: int | None = None
    item_id: int | None = None
    condition: str | None = None
    low_stock_only: bool = False
    include_inactive: bool = False
    movement_type: str | None = None
    period_id: int | None = None
    # Mantenimiento e incidencias
    maintenance_type: str | None = None
    final_status: str | None = None
    responsible_id: int | None = None
    origin: str | None = None
    incident_status: str | None = None
    priority: str | None = None
    reporter_id: int | None = None
    # Usuarios y auditoría
    role_id: int | None = None
    position_id: int | None = None
    is_active: bool | None = None
    action: str | None = None
    actor_id: int | None = None


@dataclass(frozen=True)
class FilterOptions:
    """Opciones de filtros que no tienen un catálogo propio consultable por el usuario."""

    responsibles: list[tuple[int, str]]
    reporters: list[tuple[int, str]]
    actors: list[tuple[int, str]] | None
    audit_actions: list[str] | None


class ReportService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.measurements = MeasurementService(session)
        self.inventory = InventoryService(session)
        self.maintenance = MaintenanceService(session)
        self.periods = InventoryPeriodService(session)
        self.movements = InventoryMovementRepository(session)
        self.movement_types = InventoryMovementTypeRepository(session)
        self.categories = InventoryCategoryRepository(session)
        self.items = InventoryItemRepository(session)
        self.period_repo = InventoryPeriodRepository(session)
        self.devices = DeviceRepository(session)
        self.device_service = DeviceService(session)
        self.sensors = SensorRepository(session)
        self.sensor_types = SensorTypeRepository(session)
        self.fog_collectors = FogCollectorRepository(session)
        self.incidents = IncidentReportRepository(session)
        self.users = UserRepository(session)
        self.roles = RoleRepository(session)
        self.positions = PositionRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.audit = AuditService(session)
        self.analysis = AnalysisService(session)
        self.tz = ZoneInfo(get_settings().local_timezone)

    # --- Catálogo y opciones -----------------------------------------------------

    @staticmethod
    def catalog(ctx: RequestContext) -> list[ReportDefinition]:
        return available_for(ctx.user.permission_codes if ctx.user else set())

    def filter_options(self, ctx: RequestContext) -> FilterOptions:
        codes = ctx.user.permission_codes if ctx.user else set()

        def people(users: Sequence[User]) -> list[tuple[int, str]]:
            return sorted(((u.id, u.full_name) for u in users), key=lambda x: x[1])

        # Incluye cuentas desactivadas: los reportes son históricos.
        responsibles = self.users.with_any_permission(
            [Permission.MAINTENANCE_REGISTER.value, Permission.INCIDENTS_ATTEND.value], active_only=False
        )
        reporters = self.users.with_any_permission([Permission.INCIDENTS_REPORT.value], active_only=False)
        audit = Permission.AUDIT_READ.value in codes
        return FilterOptions(
            responsibles=people(responsibles),
            reporters=people(reporters),
            actors=people(self.users.list(limit=10_000)) if audit else None,
            audit_actions=list(self.audit_logs.distinct_actions()) if audit else None,
        )

    # --- Exportación ---------------------------------------------------------------

    def build(self, ctx: RequestContext, kind: str, filters: ReportFilters) -> Report:
        """Arma el reporte (detalle, resumen y gráficos) verificando permisos y filtros obligatorios."""
        definition = BY_KIND.get(kind)
        if definition is None:
            raise BusinessRuleError("Tipo de reporte no soportado.", code="reporte_invalido")
        if definition not in self.catalog(ctx):
            raise ForbiddenError("No tiene permiso para generar este reporte.")
        for key in definition.required:
            if getattr(filters, key) is None:
                raise BusinessRuleError(
                    f"Indique el filtro «{FILTER_LABELS[key]}».",
                    code=REQUIRED_ERROR_CODES.get(key, "filtro_requerido"),
                )
        filters = self._with_default_range(filters)
        builder = getattr(self, f"_build_{kind}")
        # El análisis incluye solo las secciones que el usuario puede consultar.
        report = add_charts(kind, builder(filters, ctx) if kind == "analisis" else builder(filters))
        report.filters = [*self._describe(definition, filters), *report.filters]
        report.generated_at = utcnow().astimezone(self.tz)
        report.generated_by = ctx.user.full_name if ctx.user else None
        return report

    def export(self, ctx: RequestContext, kind: str, fmt: str, filters: ReportFilters) -> RenderedFile:
        renderer = RENDERERS.get(fmt)
        if renderer is None:
            raise BusinessRuleError("Formato no soportado.", code="formato_invalido")
        report = self.build(ctx, kind, filters)
        applied = {
            k: v
            for k, v in self._applied(BY_KIND[kind], self._with_default_range(filters)).items()
            if k != "date_range"
        }
        self.audit.record(
            ctx,
            "reporte.exportar",
            entity_type="report",
            details={"reporte": kind, "formato": fmt, "filas": len(report.rows), "filtros": applied},
        )
        self.session.commit()
        return renderer(report)

    def _with_default_range(self, f: ReportFilters) -> ReportFilters:
        date_to = f.date_to or utcnow()
        date_from = f.date_from or date_to - timedelta(days=30)
        if date_from >= date_to:
            raise BusinessRuleError("La fecha inicial debe ser anterior a la final.", code="rango_invalido")
        return replace(f, date_from=date_from, date_to=date_to)

    @staticmethod
    def _applied(definition: ReportDefinition, f: ReportFilters) -> dict[str, object]:
        """Filtros del reporte con un valor distinto del predeterminado."""
        applied: dict[str, object] = {}
        for key in definition.filters:
            if key == "date_range":
                applied[key] = (f.date_from, f.date_to)
                continue
            value = getattr(f, key)
            if value is not None and value is not False and not (key == "bucket" and value == "day"):
                applied[key] = value
        return applied

    def _describe(self, definition: ReportDefinition, f: ReportFilters) -> list[str]:
        lines: list[str] = []
        if "date_range" in definition.filters:
            lines.append(self._period_line(f))
        for key, value in self._applied(definition, f).items():
            if key in SELF_DESCRIBED:
                continue
            lines.append(f"{FILTER_LABELS[key]}: {self._value_text(key, value)}")
        if len(lines) == ("date_range" in definition.filters):
            lines.append("Sin filtros adicionales: incluye todos los registros.")
        return lines

    def _value_text(self, key: str, value: object) -> str:  # noqa: PLR0911 - una rama por filtro
        def named(entity: object, *attrs: str) -> str:
            if entity is None:
                return f"#{value} (no encontrado)"
            return " — ".join(str(getattr(entity, a)) for a in attrs if getattr(entity, a, None))

        if isinstance(value, bool):
            if key == "is_active":
                return "activas" if value else "desactivadas"
            return "sí" if value else "no"
        if key == "bucket":
            return BUCKET_LABELS.get(str(value), str(value))
        if key == "device_id":
            return named(self.devices.get(int(value)), "code", "name")  # type: ignore[arg-type]
        if key == "fog_collector_id":
            return named(self.fog_collectors.get(int(value)), "code", "name")  # type: ignore[arg-type]
        if key == "sensor_type":
            return named(self.sensor_types.get_by(code=value), "name")
        if key == "category_id":
            return named(self.categories.get(int(value)), "name")  # type: ignore[arg-type]
        if key == "item_id":
            return named(self.items.get(int(value)), "code", "name")  # type: ignore[arg-type]
        if key == "movement_type":
            return named(self.movement_types.get_by_code(str(value)), "name")
        if key in {"responsible_id", "reporter_id", "actor_id"}:
            return named(self.users.get(int(value)), "full_name")  # type: ignore[arg-type]
        if key == "role_id":
            return named(self.roles.get(int(value)), "name")  # type: ignore[arg-type]
        if key == "position_id":
            return named(self.positions.get(int(value)), "name")  # type: ignore[arg-type]
        if key == "origin":
            return ORIGIN_LABELS.get(str(value), str(value))
        if key == "connection":
            return CONNECTION_LABELS.get(str(value), str(value))
        return str(value).replace("_", " ")

    def _local(self, value: datetime | None) -> datetime | None:
        return value.astimezone(self.tz) if value else None

    def _period_line(self, f: ReportFilters) -> str:
        start, end = self._local(f.date_from), self._local(f.date_to)
        return f"Periodo: {start:%Y-%m-%d %H:%M} a {end:%Y-%m-%d %H:%M} (hora de Bolivia)"

    # --- Monitoreo IoT y volumen -----------------------------------------------------

    def _build_mediciones(self, f: ReportFilters) -> Report:
        readings, total = self.measurements.search(
            offset=0,
            limit=MAX_REPORT_ROWS,
            device_id=f.device_id,
            sensor_type_code=f.sensor_type,
            fog_collector_id=f.fog_collector_id,
            quality=f.quality,
            date_from=f.date_from,
            date_to=f.date_to,
        )
        lines: list[str] = []
        if total > MAX_REPORT_ROWS:
            lines.append(f"Se incluyen las {MAX_REPORT_ROWS} lecturas más recientes de {total}.")
        return Report(
            title="Histórico de mediciones",
            filename="historico_mediciones",
            columns=[
                "Fecha de medición",
                "Fecha de recepción",
                "Dispositivo",
                "Sensor",
                "Variable",
                "Valor",
                "Unidad",
                "Calidad",
            ],
            rows=[
                [
                    self._local(r.measured_at),
                    self._local(r.received_at),
                    r.sensor.device.code,
                    r.sensor.code,
                    r.sensor.sensor_type.name,
                    r.value,
                    r.unit,
                    r.quality,
                ]
                for r in readings
            ],
            filters=lines,
        )

    def _series_report(self, f: ReportFilters, type_code: str, title: str, filename: str) -> Report:
        series = self.measurements.series(
            sensor_type_code=type_code,
            bucket=f.bucket,
            date_from=f.date_from,
            date_to=f.date_to,
            device_id=f.device_id,
            fog_collector_id=f.fog_collector_id,
        )
        unit = series.sensor_type.unit
        incremental = series.sensor_type.aggregation == "incremental"
        value_label = f"Total ({unit})" if incremental else f"Promedio ({unit})"
        return Report(
            title=title,
            filename=filename,
            columns=[
                f"Periodo ({BUCKET_LABELS[f.bucket]})",
                value_label,
                f"Mínimo ({unit})",
                f"Máximo ({unit})",
                "Lecturas válidas",
            ],
            rows=[[p.bucket, p.value, p.min, p.max, p.count] for p in series.points],
            filters=["Solo se consideran lecturas válidas."],
        )

    def _build_volumen(self, f: ReportFilters) -> Report:
        return self._series_report(f, VOLUME_TYPE_CODE, "Volumen de agua captada", "volumen_captado")

    def _build_variable(self, f: ReportFilters) -> Report:
        if not f.sensor_type:
            raise BusinessRuleError("Indique la variable (sensor_type) del reporte.", code="variable_requerida")
        return self._series_report(
            f, f.sensor_type, f"Variable ambiental: {f.sensor_type}", f"variable_{f.sensor_type}"
        )

    def _build_inventario_stock(self, f: ReportFilters) -> Report:
        items = self.inventory.stock_report(
            include_inactive=f.include_inactive,
            category_id=f.category_id,
            condition=f.condition,
            low_stock_only=f.low_stock_only,
        )
        return Report(
            title="Stock de repuestos",
            filename="inventario_stock",
            columns=["Código", "Nombre", "Categoría", "Unidad", "Stock actual", "Stock mínimo", "Estado", "Reposición"],
            rows=[
                [
                    i.code,
                    i.name,
                    i.category.name,
                    i.unit,
                    i.current_stock,
                    i.min_stock,
                    i.condition if i.is_active else f"{i.condition} (desactivado)",
                    "Sí" if i.current_stock <= i.min_stock else "No",
                ]
                for i in items
            ],
        )

    def _build_inventario_movimientos(self, f: ReportFilters) -> Report:
        movements = self.movements.search_effective(
            date_from=f.date_from,
            date_to=f.date_to,
            item_id=f.item_id,
            category_id=f.category_id,
            movement_type_codes=[f.movement_type] if f.movement_type else None,
            limit=MAX_REPORT_ROWS,
        )
        return Report(
            title="Movimientos de inventario",
            filename="inventario_movimientos",
            columns=[
                "Fecha efectiva",
                "Fecha de registro",
                "Código",
                "Repuesto",
                "Tipo",
                "Cantidad",
                "Unidad",
                "Costo unitario (Bs)",
                "Stock anterior",
                "Stock posterior",
                "Usuario",
                "Motivo",
            ],
            rows=[
                [
                    self._local(m.occurred_at),
                    self._local(m.created_at),
                    m.item.code,
                    m.item.name,
                    m.movement_type.name,
                    m.quantity,
                    m.item.unit,
                    m.unit_cost,
                    m.stock_before,
                    m.stock_after,
                    m.user.username,
                    m.reason,
                ]
                for m in movements
            ],
        )

    def _require_period(self, f: ReportFilters) -> PeriodSummary:
        if f.period_id is None:
            raise BusinessRuleError("Indique el periodo de inventario (period_id).", code="periodo_requerido")
        return self.periods.summary(f.period_id)

    @staticmethod
    def _in_category(summary: PeriodSummary, f: ReportFilters) -> list:  # type: ignore[type-arg]
        return [b for b in summary.balances if f.category_id is None or b.item.category_id == f.category_id]

    def _build_inventario_periodo(self, f: ReportFilters) -> Report:
        summary = self._require_period(f)
        period = summary.period
        total = summary.total_value
        state = (
            "PROVISIONAL (periodo abierto)"
            if summary.provisional
            else f"Cerrado el {self._local(period.closed_at):%Y-%m-%d %H:%M}"
        )
        rows: list[list[object]] = [
            [
                b.item.code,
                b.item.name,
                b.item.unit,
                b.opening_quantity,
                b.entries_quantity,
                b.exits_quantity,
                b.maintenance_exits_quantity,
                b.adjustments_quantity,
                b.closing_quantity,
                b.average_unit_cost,
                b.closing_value,
            ]
            for b in self._in_category(summary, f)
        ]
        if f.category_id is not None:
            values = [b.closing_value for b in self._in_category(summary, f)]
            total = None if any(v is None for v in values) else sum(values, Decimal(0))  # type: ignore[arg-type]
        rows.append(["TOTAL", None, None, None, None, None, None, None, None, None, total])
        return Report(
            title=f"Resumen de inventario — {period.name}",
            filename=f"inventario_periodo_{period.start_date:%Y%m%d}",
            columns=[
                "Código",
                "Repuesto",
                "Unidad",
                "Saldo inicial",
                "Entradas",
                "Salidas",
                "Salidas por mantenimiento",
                "Ajustes por conteo",
                "Saldo final",
                "Costo promedio (Bs)",
                "Valor final (Bs)",
            ],
            rows=rows,
            filters=[
                f"Periodo: {period.start_date:%d/%m/%Y} al {period.end_date:%d/%m/%Y}",
                f"Estado: {state}",
                "Valorización: costo promedio ponderado. Un valor vacío indica entradas sin costo registrado.",
            ],
        )

    def _build_inventario_conteo(self, f: ReportFilters) -> Report:
        summary = self._require_period(f)
        period = summary.period
        counts_done = any(b.counted_quantity is not None for b in summary.balances)
        title = "Acta de conteo físico" if counts_done else "Planilla de conteo físico"
        return Report(
            title=f"{title} — {period.name}",
            filename=f"inventario_conteo_{period.start_date:%Y%m%d}",
            columns=[
                "Código",
                "Repuesto",
                "Unidad",
                "Saldo según registros",
                "Cantidad contada",
                "Diferencia",
                "Observaciones",
            ],
            rows=[
                [
                    b.item.code,
                    b.item.name,
                    b.item.unit,
                    b.theoretical_quantity,
                    b.counted_quantity,
                    b.difference,
                    "Sobrante" if (b.difference or 0) > 0 else "Faltante" if (b.difference or 0) < 0 else None,
                ]
                for b in self._in_category(summary, f)
            ],
            filters=[
                f"Periodo: {period.start_date:%d/%m/%Y} al {period.end_date:%d/%m/%Y}",
                "Responsable del conteo: ______________________    Firma: ______________",
                "Verificado por: ______________________    Firma: ______________",
            ],
        )

    def _build_inventario_kardex(self, f: ReportFilters) -> Report:
        if f.item_id is None:
            raise BusinessRuleError("Indique el repuesto (item_id) para el kardex.", code="repuesto_requerido")
        item = self.inventory.get_item(f.item_id)
        balance = self.movements.balances_before(f.date_from, [item.id]).get(item.id, Decimal(0))
        rows: list[list[object]] = [
            [self._local(f.date_from), "Saldo inicial", None, None, None, None, balance, None, None]
        ]
        for m in self.movements.search_effective(date_from=f.date_from, date_to=f.date_to, item_id=item.id):
            signed = m.quantity * m.movement_type.direction
            balance += signed
            rows.append(
                [
                    self._local(m.occurred_at),
                    m.movement_type.name,
                    m.reason,
                    m.user.username,
                    m.quantity if signed > 0 else None,
                    m.quantity if signed < 0 else None,
                    balance,
                    m.unit_cost,
                    (m.quantity * m.unit_cost).quantize(Decimal("0.01")) if m.unit_cost is not None else None,
                ]
            )
        return Report(
            title=f"Kardex — {item.code} {item.name}",
            filename=f"kardex_{item.code}",
            columns=[
                "Fecha",
                "Movimiento",
                "Detalle",
                "Usuario",
                f"Entrada ({item.unit})",
                f"Salida ({item.unit})",
                f"Saldo ({item.unit})",
                "Costo unitario (Bs)",
                "Valor entrada (Bs)",
            ],
            rows=rows,
            filters=[f"Categoría: {item.category.name} · Stock actual: {item.current_stock.normalize()} {item.unit}"],
        )

    def _build_inventario_consumo(self, f: ReportFilters) -> Report:
        records, _ = self.maintenance.search(
            offset=0,
            limit=MAX_REPORT_ROWS,
            device_id=f.device_id,
            date_from=f.date_from,
            date_to=f.date_to,
            status=MAINTENANCE_FINISHED,
        )
        totals: dict[tuple[str, str], dict[str, object]] = {}
        for record in records:
            for used in record.items:
                if f.item_id is not None and used.item_id != f.item_id:
                    continue
                if f.category_id is not None and used.item.category_id != f.category_id:
                    continue
                key = (record.device.code if record.device else "—", used.item.code)
                row = totals.setdefault(
                    key,
                    {"name": used.item.name, "unit": used.item.unit, "quantity": Decimal(0), "records": set()},
                )
                row["quantity"] += used.quantity  # type: ignore[operator]
                row["records"].add(record.id)  # type: ignore[union-attr]
        return Report(
            title="Consumo de repuestos por mantenimiento",
            filename="inventario_consumo",
            columns=["Dispositivo", "Código", "Repuesto", "Unidad", "Cantidad utilizada", "Mantenimientos"],
            rows=[
                [device, code, v["name"], v["unit"], v["quantity"], len(v["records"])]  # type: ignore[arg-type]
                for (device, code), v in sorted(totals.items())
            ],
        )

    def _build_mantenimientos(self, f: ReportFilters) -> Report:
        records, _ = self.maintenance.search(
            offset=0,
            limit=MAX_REPORT_ROWS,
            device_id=f.device_id,
            date_from=f.date_from,
            date_to=f.date_to,
            status=MAINTENANCE_FINISHED,
            maintenance_type=f.maintenance_type,
            final_status=f.final_status,
            user_id=f.responsible_id,
            from_incident=None if f.origin is None else f.origin == "incidencia",
        )
        return Report(
            title="Mantenimientos finalizados",
            filename="mantenimientos",
            columns=[
                "Fecha",
                "Dispositivo",
                "Sensor",
                "Tipo",
                "Descripción",
                "Repuestos",
                "Responsable",
                "Estado final",
                "Reporte de incidencia",
            ],
            rows=[
                [
                    self._local(r.performed_at),
                    r.device.code if r.device else None,
                    r.sensor.code if r.sensor else None,
                    r.maintenance_type,
                    r.description,
                    ", ".join(f"{i.item.code} × {i.quantity.normalize()}" for i in r.items) or None,
                    r.user.full_name,
                    r.final_status,
                    f"#{r.incident_report_id}" if r.incident_report_id else None,
                ]
                for r in records
            ],
        )

    # --- Estaciones -------------------------------------------------------------------

    def _build_dispositivos(self, f: ReportFilters) -> Report:
        now = utcnow()
        devices = self.device_service.list(
            status=f.device_status, fog_collector_id=f.fog_collector_id, connection=f.connection
        )
        rows: list[list[object]] = []
        for d in devices:
            sensors = self.sensors.list_by_device(d.id)
            location = self.device_service.current_location(d.id)
            situation = CONNECTION_LABELS[connection_state(d.last_seen_at, d.sample_interval_s, now)]
            rows.append(
                [
                    d.code,
                    d.name,
                    d.status,
                    d.fog_collector.name if d.fog_collector else None,
                    location.location.name if location and location.location else None,
                    sum(1 for s in sensors if s.status == "activo"),
                    len(sensors),
                    self._local(d.last_seen_at),
                    situation,
                    d.firmware_version,
                ]
            )
        return Report(
            title="Estado de las estaciones",
            filename="estado_estaciones",
            columns=[
                "Código",
                "Nombre",
                "Estado",
                "Atrapanieblas",
                "Ubicación",
                "Sensores activos",
                "Sensores",
                "Última comunicación",
                "Situación",
                "Firmware",
            ],
            rows=rows,
            filters=[
                f"Se considera desactualizado tras {MISSED_INTERVALS} intervalos de envío sin comunicación "
                f"(como máximo {get_settings().device_stale_minutes} minutos)."
            ],
        )

    # --- Reportes de incidencia ----------------------------------------------------------

    @staticmethod
    def _hours(start: datetime | None, end: datetime | None) -> Decimal | None:
        if start is None or end is None:
            return None
        return (Decimal((end - start).total_seconds()) / 3600).quantize(Decimal("0.1"))

    def _build_incidencias(self, f: ReportFilters) -> Report:
        reports, _ = self.incidents.search(
            offset=0,
            limit=MAX_REPORT_ROWS,
            status=f.incident_status,
            priority=f.priority,
            device_id=f.device_id,
            reported_by_id=f.reporter_id,
            assigned_to_id=f.responsible_id,
            date_from=f.date_from,
            date_to=f.date_to,
        )
        rows: list[list[object]] = []
        for r in reports:
            m = r.maintenance
            rows.append(
                [
                    r.id,
                    self._local(r.created_at),
                    r.title,
                    r.priority,
                    r.status,
                    r.reporter.full_name if r.reporter else "Sistema (detección automática)",
                    " · ".join(
                        x
                        for x in (
                            r.device.code if r.device else None,
                            f"sensor {r.sensor.code}" if r.sensor else None,
                            r.location_reference,
                        )
                        if x
                    )
                    or None,
                    m.user.full_name if m else None,
                    self._local(m.accepted_at) if m else None,
                    self._local(m.finished_at) if m else None,
                    self._hours(r.created_at, m.accepted_at) if m else None,
                    self._hours(r.created_at, m.finished_at) if m else None,
                    m.final_status if m else None,
                ]
            )
        finished = [row[11] for row in rows if row[11] is not None]
        notes = [f"Reportes: {len(rows)} · finalizados: {len(finished)}"]
        if finished:
            average = sum(finished, Decimal(0)) / len(finished)  # type: ignore[arg-type]
            notes.append(
                f"Tiempo promedio desde el reporte hasta la finalización: {average.quantize(Decimal('0.1'))} h"
            )
        return Report(
            title="Reportes de incidencia y su atención",
            filename="reportes_incidencia",
            columns=[
                "Nro.",
                "Fecha del reporte",
                "Título",
                "Prioridad",
                "Estado",
                "Reportado por",
                "Componente / lugar",
                "Asignado a",
                "Aceptado",
                "Finalizado",
                "Horas hasta aceptar",
                "Horas hasta finalizar",
                "Estado final del componente",
            ],
            rows=rows,
            filters=notes,
        )

    # --- Usuarios y auditoría ----------------------------------------------------------

    def _build_usuarios(self, f: ReportFilters) -> Report:
        users, _ = self.users.search(
            offset=0, limit=MAX_REPORT_ROWS, is_active=f.is_active, role_id=f.role_id, position_id=f.position_id
        )
        rows: list[list[object]] = []
        for u in users:
            p = u.profile
            ci = None
            if p and p.ci_number:
                ci = " ".join(
                    x for x in (p.ci_number + (f"-{p.ci_complement}" if p.ci_complement else ""), p.ci_issued_in) if x
                )
            rows.append(
                [
                    u.username,
                    u.full_name,
                    ci,
                    p.mobile_phone if p else None,
                    p.institutional_email if p else None,
                    p.position.name if p and p.position else None,
                    ", ".join(r.name for r in u.roles),
                    "Activa" if u.is_active else "Desactivada",
                    self._local(u.last_login_at),
                    "Sí" if u.profile_complete else "No",
                ]
            )
        return Report(
            title="Usuarios registrados",
            filename="usuarios",
            columns=[
                "Usuario",
                "Nombre completo",
                "CI",
                "Celular",
                "Correo institucional",
                "Cargo",
                "Roles",
                "Cuenta",
                "Último acceso",
                "Perfil completo",
            ],
            rows=rows,
            filters=["Contiene datos personales: manéjelo solo dentro de la institución."],
        )

    def _build_auditoria(self, f: ReportFilters) -> Report:
        logs, total = self.audit_logs.search(
            offset=0,
            limit=MAX_REPORT_ROWS,
            user_id=f.actor_id,
            action=f.action,
            date_from=f.date_from,
            date_to=f.date_to,
        )
        names = {u.id: u.full_name for u in self.users.list(limit=10_000)}
        notes = [f"Se incluyen los {MAX_REPORT_ROWS} registros más recientes de {total}."] if total > len(logs) else []
        return Report(
            title="Auditoría",
            filename="auditoria",
            columns=["Fecha", "Usuario", "Acción", "Entidad", "Identificador", "Dirección IP", "Detalle"],
            rows=[
                [
                    self._local(log.created_at),
                    names.get(log.user_id, "Sistema") if log.user_id else "Sistema",
                    log.action,
                    log.entity_type,
                    log.entity_id,
                    str(log.ip_address) if log.ip_address else None,
                    json.dumps(log.details, ensure_ascii=False, default=str) if log.details else None,
                ]
                for log in logs
            ],
            filters=notes,
        )

    # --- Análisis estadístico --------------------------------------------------------

    def _build_analisis(self, f: ReportFilters, ctx: RequestContext) -> Report:  # noqa: PLR0915 - una sección por módulo
        a = self.analysis.analyze(
            ctx,
            date_from=f.date_from,
            date_to=f.date_to,
            device_id=f.device_id,
            fog_collector_id=f.fog_collector_id,
        )
        rows: list[list[object]] = []
        charts: list[Chart] = []
        summary: list[tuple[str, str]] = []

        def add(section: str, label: str, value: object, unit: str | None = None, note: str | None = None) -> None:
            rows.append([section, label, round(value, 3) if isinstance(value, float) else value, unit, note])

        def stats(section: str, name: str, s: dict[str, object], unit: str) -> None:
            note = f"n = {s['n']} días"
            for key, label in (
                ("mean", "media"),
                ("median", "mediana"),
                ("std", "desviación estándar"),
                ("min", "mínimo"),
                ("max", "máximo"),
            ):
                add(section, f"{name}: {label}", s[key], unit, note)

        def counts(title: str, data: dict[str, int], unit: str) -> Chart:
            ranked = sorted(data.items(), key=lambda kv: -kv[1])
            return Chart(
                title,
                "bar",
                [readable(k) for k, _ in ranked],
                [Series(unit.capitalize(), [float(n) for _, n in ranked])],
                unit,
            )

        if capture := a.get("capture"):
            section = "Captación de agua"
            add(section, "Volumen total captado", capture["total"], "L")
            add(section, "Días con datos", capture["days_with_data"], "días")
            add(section, "Días con captación", capture["days_with_capture"], "días")
            add(section, "Día de mayor captación", capture["best_day"])
            stats(section, "Volumen diario", capture["daily"], "L/día")
            for fog in capture["by_fog_collector"]:
                share = f"{fog['share'] * 100:.1f} % del total" if fog["share"] is not None else None
                add(section, f"Total en {fog['name']}", fog["total"], "L", share)
            summary += [
                ("Volumen total captado", f"{capture['total']:.2f} L".replace(".", ",")),
                (
                    "Promedio diario",
                    f"{capture['daily']['mean']:.2f} L/día".replace(".", ",")
                    if capture["daily"]["mean"] is not None
                    else "—",
                ),
                ("Días con captación", f"{capture['days_with_capture']} de {capture['days_with_data']}"),
            ]
            charts.append(
                Chart(
                    "Volumen captado por día",
                    "bar",
                    [p["date"] for p in capture["series"]],
                    [Series("Volumen (L)", [p["value"] for p in capture["series"]])],
                    "L",
                )
            )
            if capture["by_fog_collector"]:
                charts.append(
                    Chart(
                        "Volumen captado por atrapanieblas",
                        "bar",
                        [fog["name"] for fog in capture["by_fog_collector"]],
                        [Series("Volumen (L)", [fog["total"] for fog in capture["by_fog_collector"]])],
                        "L",
                        horizontal=True,
                    )
                )
        for variable in a.get("variables", []):
            stats("Variables ambientales", variable["name"], variable, variable["unit"])
        correlations = a.get("correlations", [])
        for c in correlations:
            add(
                "Correlación con el volumen diario",
                f"{c['name']} (r de Pearson)",
                c["r"],
                None,
                f"{c['strength']}; n = {c['n']} días",
            )
        measured = [c for c in correlations if c["r"] is not None]
        if measured:
            charts.append(
                Chart(
                    "Correlación de cada variable con el volumen diario",
                    "bar",
                    [c["name"] for c in measured],
                    [Series("r de Pearson", [c["r"] for c in measured])],
                    "coeficiente de Pearson (−1 a 1); no implica causalidad",
                    horizontal=True,
                )
            )
        if quality := a.get("quality"):
            section = "Calidad de los datos"
            add(section, "Lecturas recibidas", quality["total"], "lecturas")
            for key, count in quality["by_quality"].items():
                add(section, f"Lecturas: {readable(key).lower()}", count, "lecturas")
            for device in quality["by_device"]:
                add(
                    section,
                    f"Lecturas válidas en {device['device']}",
                    round(device["valid_share"] * 100, 1),
                    "%",
                    f"de {device['total']} lecturas",
                )
            if quality["valid_share"] is not None:
                summary.append(("Lecturas válidas", f"{quality['valid_share'] * 100:.1f} %".replace(".", ",")))
            if quality["by_quality"]:
                charts.append(counts("Lecturas por calidad", quality["by_quality"], "lecturas"))
        if maintenance := a.get("maintenance"):
            section = "Mantenimiento"
            add(section, "Mantenimientos finalizados", maintenance["total"], "mantenimientos")
            add(section, "Originados en reportes de incidencia", maintenance["from_incidents"], "mantenimientos")
            add(section, "Con uso de repuestos", maintenance["with_parts"], "mantenimientos")
            for key, count in maintenance["by_type"].items():
                add(section, f"Tipo: {readable(key).lower()}", count, "mantenimientos")
            for key, count in maintenance["by_final_status"].items():
                add(section, f"Estado final: {readable(key).lower()}", count, "mantenimientos")
            if maintenance["by_type"]:
                charts.append(counts("Mantenimientos por tipo", maintenance["by_type"], "mantenimientos"))
        if incidents := a.get("incidents"):
            section = "Reportes de incidencia"
            add(section, "Reportes registrados", incidents["total"], "reportes")
            for key, count in incidents["by_status"].items():
                add(section, f"Estado: {readable(key).lower()}", count, "reportes")
            for key, count in incidents["by_priority"].items():
                add(section, f"Prioridad: {readable(key).lower()}", count, "reportes")
            stats(section, "Horas hasta aceptar", incidents["hours_to_accept"], "h")
            stats(section, "Horas hasta finalizar", incidents["hours_to_finish"], "h")
            if incidents["by_status"]:
                charts.append(counts("Reportes de incidencia por estado", incidents["by_status"], "reportes"))
        if inventory := a.get("inventory"):
            section = "Inventario"
            add(section, "Repuestos con stock bajo", inventory["low_stock"], "repuestos")
            for item in inventory["top_consumed"]:
                add(section, f"Consumo de {item['code']} {item['name']}", item["quantity"], item["unit"])
        for row in rows:  # las estadísticas sin datos quedan vacías, no en 0
            if row[2] is None and row[4] is None:
                row[4] = "Sin datos en el periodo"
        report = Report(
            title="Análisis estadístico del periodo",
            filename="analisis_estadistico",
            columns=["Sección", "Indicador", "Valor", "Unidad", "Observación"],
            rows=rows,
            filters=["Solo lecturas válidas; los días sin datos no se cuentan como cero."],
        )
        report.summary, report.charts = summary, charts
        return report
