"""Endpoints de inventario de repuestos y de mantenimiento."""

import csv
import io
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, status

from app.business.services.inventory_period_service import InventoryPeriodService, PeriodSummary
from app.business.services.inventory_service import InventoryService
from app.business.services.maintenance_service import MaintenanceService, UsedPart
from app.core.permissions import Permission
from app.data.models.inventory import InventoryMovement, MaintenanceRecord
from app.presentation.api.deps import AuthContext, DbSession, require
from app.presentation.schemas.common import Page
from app.presentation.schemas.inventory import (
    BalanceOut,
    CategoryIn,
    CategoryOut,
    CountsIn,
    ItemIn,
    ItemOut,
    ItemSummaryOut,
    ItemUpdate,
    MaintenanceIn,
    MaintenanceItemOut,
    MaintenanceOut,
    MaintenanceStatus,
    MaintenanceType,
    MovementIn,
    MovementOut,
    MovementTypeOut,
    PeriodIn,
    PeriodOut,
    PeriodSummaryOut,
)

router = APIRouter(tags=["Inventario y mantenimiento"])

InventoryReader = Annotated[AuthContext, Depends(require(Permission.INVENTORY_READ))]
InventoryManager = Annotated[AuthContext, Depends(require(Permission.INVENTORY_MANAGE))]
MaintenanceReader = Annotated[AuthContext, Depends(require(Permission.MAINTENANCE_READ))]
MaintenanceWriter = Annotated[AuthContext, Depends(require(Permission.MAINTENANCE_REGISTER))]
ReportFormat = Literal["json", "csv"]


def to_movement_out(movement: InventoryMovement) -> MovementOut:
    return MovementOut.model_validate(movement).model_copy(update={"username": movement.user.username})


def to_maintenance_out(record: MaintenanceRecord) -> MaintenanceOut:
    return MaintenanceOut(
        id=record.id,
        status=record.status,  # type: ignore[arg-type]
        incident_report_id=record.incident_report_id,
        device_id=record.device_id,
        device_code=record.device.code if record.device else None,
        sensor_id=record.sensor_id,
        sensor_code=record.sensor.code if record.sensor else None,
        performed_at=record.performed_at,
        user_id=record.user_id,
        username=record.user.username,
        user_full_name=record.user.full_name,
        maintenance_type=record.maintenance_type,  # type: ignore[arg-type]
        description=record.description,
        final_status=record.final_status,  # type: ignore[arg-type]
        accepted_at=record.accepted_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
        created_at=record.created_at,
        items=[
            MaintenanceItemOut(
                item_id=i.item_id,
                item_code=i.item.code,
                item_name=i.item.name,
                quantity=i.quantity,
                movement_id=i.movement_id,
            )
            for i in record.items
        ],
    )


def csv_response(filename: str, header: list[str], rows: list[list[object]]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    # BOM para que Excel reconozca UTF-8 (acentos).
    return Response(
        content="﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Categorías ------------------------------------------------------------


@router.get("/inventory/categories", response_model=list[CategoryOut])
def list_categories(db: DbSession, _: InventoryReader) -> list[CategoryOut]:
    return [CategoryOut.model_validate(c) for c in InventoryService(db).list_categories()]


@router.post("/inventory/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryIn, db: DbSession, auth: InventoryManager) -> CategoryOut:
    category = InventoryService(db).create_category(auth.ctx, name=payload.name, description=payload.description)
    return CategoryOut.model_validate(category)


@router.get("/inventory/movement-types", response_model=list[MovementTypeOut])
def list_movement_types(db: DbSession, _: InventoryReader) -> list[MovementTypeOut]:
    return [MovementTypeOut.model_validate(t) for t in InventoryService(db).list_movement_types()]


# --- Repuestos -------------------------------------------------------------


@router.get("/inventory/items", response_model=Page[ItemOut])
def list_items(
    db: DbSession,
    _: InventoryReader,
    q: str | None = None,
    category_id: int | None = None,
    is_active: bool | None = True,
    device_id: int | None = Query(default=None, description="Repuestos compatibles con el dispositivo"),
    sensor_id: int | None = Query(default=None, description="Repuestos compatibles con el sensor"),
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> Page[ItemOut]:
    items, total = InventoryService(db).search_items(
        offset=offset,
        limit=limit,
        q=q,
        category_id=category_id,
        is_active=is_active,
        device_id=device_id,
        sensor_id=sensor_id,
    )
    return Page(items=[ItemOut.model_validate(i) for i in items], total=total, offset=offset, limit=limit)


@router.post("/inventory/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemIn, db: DbSession, auth: InventoryManager) -> ItemOut:
    data = payload.model_dump(
        exclude={"initial_stock", "initial_unit_cost", "compatible_device_ids", "compatible_sensor_ids"}
    )
    item = InventoryService(db).create_item(
        auth.ctx,
        data,
        initial_stock=payload.initial_stock,
        initial_unit_cost=payload.initial_unit_cost,
        device_ids=payload.compatible_device_ids,
        sensor_ids=payload.compatible_sensor_ids,
    )
    return ItemOut.model_validate(item)


@router.get("/inventory/items/{item_id}", response_model=ItemOut)
def get_item(item_id: int, db: DbSession, _: InventoryReader) -> ItemOut:
    return ItemOut.model_validate(InventoryService(db).get_item(item_id))


@router.put("/inventory/items/{item_id}", response_model=ItemOut)
def update_item(item_id: int, payload: ItemUpdate, db: DbSession, auth: InventoryManager) -> ItemOut:
    data = payload.model_dump(exclude_unset=True, exclude={"compatible_device_ids", "compatible_sensor_ids"})
    item = InventoryService(db).update_item(
        auth.ctx,
        item_id,
        data,
        device_ids=payload.compatible_device_ids,
        sensor_ids=payload.compatible_sensor_ids,
    )
    return ItemOut.model_validate(item)


@router.delete("/inventory/items/{item_id}", response_model=ItemOut, summary="Desactivar repuesto (no se elimina)")
def deactivate_item(item_id: int, db: DbSession, auth: InventoryManager) -> ItemOut:
    return ItemOut.model_validate(InventoryService(db).deactivate_item(auth.ctx, item_id))


@router.post("/inventory/items/{item_id}/movements", response_model=MovementOut, status_code=status.HTTP_201_CREATED)
def register_movement(item_id: int, payload: MovementIn, db: DbSession, auth: InventoryManager) -> MovementOut:
    movement = InventoryService(db).register_movement(
        auth.ctx,
        item_id,
        movement_type_code=payload.movement_type,
        quantity=payload.quantity,
        reason=payload.reason,
        unit_cost=payload.unit_cost,
    )
    return to_movement_out(movement)


@router.get("/inventory/items/{item_id}/movements", response_model=Page[MovementOut])
def list_item_movements(
    item_id: int,
    db: DbSession,
    _: InventoryReader,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> Page[MovementOut]:
    items, total = InventoryService(db).search_movements(offset=offset, limit=limit, item_id=item_id)
    return Page(items=[to_movement_out(m) for m in items], total=total, offset=offset, limit=limit)


@router.get("/inventory/alerts/low-stock", response_model=list[ItemOut])
def low_stock_alerts(db: DbSession, _: InventoryReader) -> list[ItemOut]:
    return [ItemOut.model_validate(i) for i in InventoryService(db).low_stock()]


@router.get("/inventory/reports/stock", response_model=list[ItemOut])
def stock_report(
    db: DbSession, _: InventoryReader, format: ReportFormat = "json", include_inactive: bool = False
) -> list[ItemOut] | Response:
    items = [ItemOut.model_validate(i) for i in InventoryService(db).stock_report(include_inactive=include_inactive)]
    if format == "csv":
        return csv_response(
            "reporte_stock.csv",
            [
                "Código",
                "Nombre",
                "Categoría",
                "Unidad",
                "Stock actual",
                "Stock mínimo",
                "Estado",
                "Activo",
                "Stock bajo",
            ],
            [
                [
                    i.code,
                    i.name,
                    i.category.name,
                    i.unit,
                    i.current_stock,
                    i.min_stock,
                    i.condition,
                    "sí" if i.is_active else "no",
                    "sí" if i.low_stock else "no",
                ]
                for i in items
            ],
        )
    return items


@router.get("/inventory/reports/movements", response_model=Page[MovementOut])
def movements_report(
    db: DbSession,
    _: InventoryReader,
    format: ReportFormat = "json",
    item_id: int | None = None,
    movement_type: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=10_000)] = 1000,
) -> Page[MovementOut] | Response:
    movements, total = InventoryService(db).search_movements(
        offset=offset,
        limit=limit,
        item_id=item_id,
        movement_type_code=movement_type,
        date_from=date_from,
        date_to=date_to,
    )
    if format == "csv":
        return csv_response(
            "reporte_movimientos.csv",
            [
                "Fecha",
                "Código",
                "Repuesto",
                "Tipo",
                "Cantidad",
                "Stock anterior",
                "Stock posterior",
                "Usuario",
                "Motivo",
            ],
            [
                [
                    m.created_at.isoformat(),
                    m.item.code,
                    m.item.name,
                    m.movement_type.name,
                    m.quantity,
                    m.stock_before,
                    m.stock_after,
                    m.user.username,
                    m.reason,
                ]
                for m in movements
            ],
        )
    return Page(items=[to_movement_out(m) for m in movements], total=total, offset=offset, limit=limit)


# --- Inventario periódico ----------------------------------------------------


def to_period_summary(summary: PeriodSummary) -> PeriodSummaryOut:
    balances = [
        BalanceOut(
            item=ItemSummaryOut.model_validate(b.item),
            opening_quantity=b.opening_quantity,
            entries_quantity=b.entries_quantity,
            exits_quantity=b.exits_quantity,
            maintenance_exits_quantity=b.maintenance_exits_quantity,
            adjustments_quantity=b.adjustments_quantity,
            theoretical_quantity=b.theoretical_quantity,
            counted_quantity=b.counted_quantity,
            difference=b.difference,
            closing_quantity=b.closing_quantity,
            opening_value=b.opening_value,
            entries_value=b.entries_value,
            average_unit_cost=b.average_unit_cost,
            closing_value=b.closing_value,
        )
        for b in summary.balances
    ]
    counted = sum(1 for b in summary.balances if b.counted_quantity is not None)
    return PeriodSummaryOut(
        period=PeriodOut.model_validate(summary.period),
        provisional=summary.provisional,
        counted_items=counted,
        pending_count_items=sum(1 for b in summary.balances if b.counted_quantity is None and b.item.is_active),
        total_value=summary.total_value,
        balances=balances,
    )


@router.get("/inventory/periods", response_model=list[PeriodOut])
def list_periods(db: DbSession, _: InventoryReader) -> list[PeriodOut]:
    return [PeriodOut.model_validate(p) for p in InventoryPeriodService(db).list()]


@router.post("/inventory/periods", response_model=PeriodOut, status_code=status.HTTP_201_CREATED)
def create_period(payload: PeriodIn, db: DbSession, auth: InventoryManager) -> PeriodOut:
    period = InventoryPeriodService(db).create(
        auth.ctx, name=payload.name, start_date=payload.start_date, end_date=payload.end_date, notes=payload.notes
    )
    return PeriodOut.model_validate(period)


@router.get(
    "/inventory/periods/{period_id}",
    response_model=PeriodSummaryOut,
    summary="Resumen del periodo y planilla de conteo físico",
)
def get_period(period_id: int, db: DbSession, _: InventoryReader) -> PeriodSummaryOut:
    return to_period_summary(InventoryPeriodService(db).summary(period_id))


@router.put("/inventory/periods/{period_id}/counts", response_model=PeriodSummaryOut, summary="Registrar conteo físico")
def register_counts(period_id: int, payload: CountsIn, db: DbSession, auth: InventoryManager) -> PeriodSummaryOut:
    service = InventoryPeriodService(db)
    service.register_counts(auth.ctx, period_id, [c.model_dump() for c in payload.counts])
    return to_period_summary(service.summary(period_id))


@router.post(
    "/inventory/periods/{period_id}/close",
    response_model=PeriodSummaryOut,
    summary="Cerrar periodo: ajustes por conteo, saldos congelados y valorización",
)
def close_period(period_id: int, db: DbSession, auth: InventoryManager) -> PeriodSummaryOut:
    return to_period_summary(InventoryPeriodService(db).close(auth.ctx, period_id))


# --- Mantenimiento ---------------------------------------------------------


@router.get("/maintenance", response_model=Page[MaintenanceOut])
def list_maintenance(
    db: DbSession,
    _: MaintenanceReader,
    device_id: int | None = None,
    sensor_id: int | None = None,
    maintenance_type: MaintenanceType | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    status: MaintenanceStatus | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> Page[MaintenanceOut]:
    records, total = MaintenanceService(db).search(
        offset=offset,
        limit=limit,
        device_id=device_id,
        sensor_id=sensor_id,
        maintenance_type=maintenance_type,
        date_from=date_from,
        date_to=date_to,
        status=status,
    )
    return Page(items=[to_maintenance_out(r) for r in records], total=total, offset=offset, limit=limit)


@router.post("/maintenance", response_model=MaintenanceOut, status_code=status.HTTP_201_CREATED)
def register_maintenance(payload: MaintenanceIn, db: DbSession, auth: MaintenanceWriter) -> MaintenanceOut:
    record = MaintenanceService(db).register(
        auth.ctx,
        device_id=payload.device_id,
        sensor_id=payload.sensor_id,
        performed_at=payload.performed_at,
        maintenance_type=payload.maintenance_type,
        description=payload.description,
        final_status=payload.final_status,
        parts=[UsedPart(item_id=p.item_id, quantity=p.quantity) for p in payload.parts],
    )
    return to_maintenance_out(record)


@router.get("/maintenance/{record_id}", response_model=MaintenanceOut)
def get_maintenance(record_id: int, db: DbSession, _: MaintenanceReader) -> MaintenanceOut:
    return to_maintenance_out(MaintenanceService(db).get(record_id))
