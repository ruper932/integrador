"""Exportación de reportes generados en el servidor."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import AwareDatetime, BaseModel, Field

from app.business.services.report_catalog import FILTER_LABELS
from app.business.services.report_service import ReportFilters, ReportService
from app.core.permissions import Permission
from app.presentation.api.deps import AuthContext, DbSession, require
from app.presentation.schemas.incidents import IncidentStatus, Priority
from app.presentation.schemas.inventory import FinalStatus, ItemCondition, MaintenanceType
from app.presentation.schemas.iot import Bucket, Connection, DeviceStatus

router = APIRouter(tags=["Reportes"])

ReportGenerator = Annotated[AuthContext, Depends(require(Permission.REPORTS_GENERATE))]
ReportKind = Literal[
    "analisis",
    "volumen",
    "variable",
    "mediciones",
    "dispositivos",
    "inventario_stock",
    "inventario_movimientos",
    "inventario_periodo",
    "inventario_conteo",
    "inventario_kardex",
    "inventario_consumo",
    "mantenimientos",
    "incidencias",
    "usuarios",
    "auditoria",
]
Quality = Literal["valida", "sin_dato", "fuera_de_rango", "unidad_invalida", "invalida"]


class ReportFilterOut(BaseModel):
    key: str
    label: str
    required: bool


class ReportDefinitionOut(BaseModel):
    kind: str
    module: str
    label: str
    description: str
    filters: list[ReportFilterOut]


class PersonOption(BaseModel):
    id: int
    full_name: str


class FilterOptionsOut(BaseModel):
    responsibles: list[PersonOption]
    reporters: list[PersonOption]
    actors: list[PersonOption] | None
    audit_actions: list[str] | None


@router.get(
    "/reports/catalog",
    response_model=list[ReportDefinitionOut],
    summary="Reportes que el usuario puede generar, agrupados por módulo, con sus filtros",
)
def report_catalog(_db: DbSession, auth: ReportGenerator) -> list[ReportDefinitionOut]:
    return [
        ReportDefinitionOut(
            kind=r.kind,
            module=r.module,
            label=r.label,
            description=r.description,
            filters=[ReportFilterOut(key=k, label=FILTER_LABELS[k], required=k in r.required) for k in r.filters],
        )
        for r in ReportService.catalog(auth.ctx)
    ]


@router.get("/reports/filter-options", response_model=FilterOptionsOut, summary="Opciones de filtros de personas")
def report_filter_options(db: DbSession, auth: ReportGenerator) -> FilterOptionsOut:
    options = ReportService(db).filter_options(auth.ctx)

    def people(rows: list[tuple[int, str]] | None) -> list[PersonOption] | None:
        return None if rows is None else [PersonOption(id=i, full_name=n) for i, n in rows]

    return FilterOptionsOut(
        responsibles=people(options.responsibles) or [],
        reporters=people(options.reporters) or [],
        actors=people(options.actors),
        audit_actions=options.audit_actions,
    )


def report_filters(  # noqa: PLR0913 - cada filtro es un parámetro de consulta documentado
    date_from: AwareDatetime | None = Query(default=None, description="Por defecto, 30 días antes de date_to"),
    date_to: AwareDatetime | None = None,
    bucket: Bucket = "day",
    device_id: int | None = None,
    sensor_type: str | None = None,
    fog_collector_id: int | None = None,
    quality: Quality | None = None,
    device_status: DeviceStatus | None = None,
    connection: Connection | None = Query(default=None, description="Situación de comunicación de la estación"),
    category_id: int | None = None,
    item_id: int | None = Query(default=None, description="Repuesto (kardex, movimientos, consumo)"),
    condition: ItemCondition | None = None,
    low_stock_only: bool = False,
    include_inactive: bool = False,
    movement_type: str | None = Query(default=None, max_length=40),
    period_id: int | None = Query(default=None, description="Periodo de inventario (resumen y conteo)"),
    maintenance_type: MaintenanceType | None = None,
    final_status: FinalStatus | None = None,
    responsible_id: int | None = Query(default=None, description="Responsable del mantenimiento o asignado"),
    origin: Literal["incidencia", "directo"] | None = None,
    incident_status: IncidentStatus | None = None,
    priority: Priority | None = None,
    reporter_id: int | None = None,
    role_id: int | None = None,
    position_id: int | None = None,
    is_active: bool | None = None,
    action: str | None = Query(default=None, max_length=80),
    actor_id: int | None = None,
) -> ReportFilters:
    return ReportFilters(**locals())


Filters = Annotated[ReportFilters, Depends(report_filters)]


class SeriesOut(BaseModel):
    name: str
    values: list[float | None]


class ChartOut(BaseModel):
    title: str
    kind: Literal["bar", "line"]
    unit: str
    horizontal: bool
    categories: list[str]
    series: list[SeriesOut]


class SummaryItemOut(BaseModel):
    label: str
    value: str


class ReportChartsOut(BaseModel):
    title: str
    rows: int
    criteria: list[str] = Field(description="Filtros aplicados y notas, tal como aparecen en el archivo exportado")
    summary: list[SummaryItemOut]
    charts: list[ChartOut]


@router.get(
    "/reports/charts",
    response_model=ReportChartsOut,
    summary="Resumen y gráficos de un reporte (los mismos que llevan el Excel y el PDF)",
)
def report_charts(db: DbSession, auth: ReportGenerator, report: ReportKind, filters: Filters) -> ReportChartsOut:
    built = ReportService(db).build(auth.ctx, report, filters)
    return ReportChartsOut(
        title=built.title,
        rows=len(built.rows),
        criteria=built.filters,
        summary=[SummaryItemOut(label=label, value=value) for label, value in built.summary],
        charts=[
            ChartOut(
                title=c.title,
                kind=c.kind,  # type: ignore[arg-type]
                unit=c.unit,
                horizontal=c.horizontal,
                categories=c.categories,
                series=[SeriesOut(name=s.name, values=s.values) for s in c.series],
            )
            for c in built.charts
        ],
    )


@router.get(
    "/reports/export",
    summary="Exportar un reporte en CSV, Excel o PDF (Excel y PDF incluyen resumen y gráficos)",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}, "application/pdf": {}}}},
)
def export_report(
    db: DbSession,
    auth: ReportGenerator,
    report: ReportKind,
    filters: Filters,
    format: Literal["csv", "xlsx", "pdf"] = "xlsx",
) -> Response:
    rendered = ReportService(db).export(auth.ctx, report, format, filters)
    return Response(
        content=rendered.content,
        media_type=rendered.media_type,
        headers={"Content-Disposition": f'attachment; filename="{rendered.filename}"'},
    )
