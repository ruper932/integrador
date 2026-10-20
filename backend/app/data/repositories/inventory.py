"""Repositorios de inventario y mantenimiento."""

from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import case, func, select

from app.data.models.inventory import (
    InventoryCategory,
    InventoryCount,
    InventoryItem,
    InventoryItemCompatibility,
    InventoryMovement,
    InventoryMovementType,
    InventoryPeriod,
    InventoryPeriodBalance,
    MaintenanceItem,
    MaintenanceRecord,
)
from app.data.repositories.base import Repository


class InventoryCategoryRepository(Repository[InventoryCategory]):
    model = InventoryCategory

    def get_by_name(self, name: str) -> InventoryCategory | None:
        return self.session.scalars(select(InventoryCategory).where(InventoryCategory.name == name)).first()


class InventoryItemRepository(Repository[InventoryItem]):
    model = InventoryItem

    def get_by_code(self, code: str) -> InventoryItem | None:
        return self.session.scalars(select(InventoryItem).where(InventoryItem.code == code)).first()

    def search(
        self,
        *,
        offset: int,
        limit: int,
        category_id: int | None = None,
        is_active: bool | None = None,
        q: str | None = None,
        device_id: int | None = None,
        sensor_id: int | None = None,
    ) -> tuple[Sequence[InventoryItem], int]:
        stmt = select(InventoryItem).order_by(InventoryItem.name)
        filters: list[Any] = []
        if category_id is not None:
            filters.append(InventoryItem.category_id == category_id)
        if is_active is not None:
            filters.append(InventoryItem.is_active.is_(is_active))
        if q:
            pattern = f"%{q}%"
            filters.append(InventoryItem.name.ilike(pattern) | InventoryItem.code.ilike(pattern))
        if device_id is not None or sensor_id is not None:
            compat = select(InventoryItemCompatibility.item_id)
            if device_id is not None:
                compat = compat.where(InventoryItemCompatibility.device_id == device_id)
            if sensor_id is not None:
                compat = compat.where(InventoryItemCompatibility.sensor_id == sensor_id)
            filters.append(InventoryItem.id.in_(compat))
        return self.paginate(stmt.where(*filters), offset=offset, limit=limit)

    def low_stock(self) -> Sequence[InventoryItem]:
        stmt = (
            select(InventoryItem)
            .where(InventoryItem.is_active.is_(True), InventoryItem.current_stock <= InventoryItem.min_stock)
            .order_by(InventoryItem.current_stock - InventoryItem.min_stock, InventoryItem.name)
        )
        return self.session.scalars(stmt).unique().all()

    def all_for_report(
        self,
        *,
        include_inactive: bool,
        category_id: int | None = None,
        condition: str | None = None,
        low_stock_only: bool = False,
    ) -> Sequence[InventoryItem]:
        stmt = select(InventoryItem).order_by(InventoryItem.category_id, InventoryItem.name)
        if not include_inactive:
            stmt = stmt.where(InventoryItem.is_active.is_(True))
        if category_id is not None:
            stmt = stmt.where(InventoryItem.category_id == category_id)
        if condition:
            stmt = stmt.where(InventoryItem.condition == condition)
        if low_stock_only:
            stmt = stmt.where(InventoryItem.current_stock <= InventoryItem.min_stock)
        return self.session.scalars(stmt).unique().all()


class InventoryMovementTypeRepository(Repository[InventoryMovementType]):
    model = InventoryMovementType

    def get_by_code(self, code: str) -> InventoryMovementType | None:
        return self.session.scalars(select(InventoryMovementType).where(InventoryMovementType.code == code)).first()


class InventoryMovementRepository(Repository[InventoryMovement]):
    model = InventoryMovement

    def search(
        self,
        *,
        offset: int,
        limit: int,
        item_id: int | None = None,
        movement_type_code: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[Sequence[InventoryMovement], int]:
        stmt = select(InventoryMovement).order_by(InventoryMovement.created_at.desc(), InventoryMovement.id.desc())
        filters: list[Any] = []
        if item_id is not None:
            filters.append(InventoryMovement.item_id == item_id)
        if movement_type_code:
            stmt = stmt.join(InventoryMovementType, InventoryMovementType.id == InventoryMovement.movement_type_id)
            filters.append(InventoryMovementType.code == movement_type_code)
        if date_from:
            filters.append(InventoryMovement.created_at >= date_from)
        if date_to:
            filters.append(InventoryMovement.created_at <= date_to)
        return self.paginate(stmt.where(*filters), offset=offset, limit=limit)

    def search_effective(
        self,
        *,
        date_from: datetime | None,
        date_to: datetime | None,
        item_id: int | None = None,
        movement_type_codes: Sequence[str] | None = None,
        category_id: int | None = None,
        limit: int = 50_000,
    ) -> Sequence[InventoryMovement]:
        """Movimientos por fecha efectiva, en orden cronológico (kardex y reportes)."""
        stmt = select(InventoryMovement).join(
            InventoryMovementType, InventoryMovementType.id == InventoryMovement.movement_type_id
        )
        if item_id is not None:
            stmt = stmt.where(InventoryMovement.item_id == item_id)
        if category_id is not None:
            stmt = stmt.join(InventoryItem, InventoryItem.id == InventoryMovement.item_id).where(
                InventoryItem.category_id == category_id
            )
        if movement_type_codes:
            stmt = stmt.where(InventoryMovementType.code.in_(movement_type_codes))
        if date_from:
            stmt = stmt.where(InventoryMovement.occurred_at >= date_from)
        if date_to:
            stmt = stmt.where(InventoryMovement.occurred_at < date_to)
        stmt = stmt.order_by(InventoryMovement.occurred_at, InventoryMovement.id).limit(limit)
        return self.session.scalars(stmt).unique().all()

    def balances_before(self, moment: datetime, item_ids: Sequence[int] | None = None) -> dict[int, Decimal]:
        """Saldo físico de cada repuesto justo antes de `moment` (según fecha efectiva)."""
        signed = InventoryMovement.quantity * InventoryMovementType.direction
        stmt = (
            select(InventoryMovement.item_id, func.coalesce(func.sum(signed), 0))
            .join(InventoryMovementType, InventoryMovementType.id == InventoryMovement.movement_type_id)
            .where(InventoryMovement.occurred_at < moment)
            .group_by(InventoryMovement.item_id)
        )
        if item_ids is not None:
            stmt = stmt.where(InventoryMovement.item_id.in_(item_ids))
        return {item_id: Decimal(total) for item_id, total in self.session.execute(stmt)}

    def item_ids_with_movements_before(self, moment: datetime) -> set[int]:
        stmt = select(InventoryMovement.item_id).where(InventoryMovement.occurred_at < moment).distinct()
        return set(self.session.scalars(stmt).all())

    def totals_between(self, start: datetime, end: datetime) -> dict[tuple[int, str], dict[str, Any]]:
        """Cantidades y valores por repuesto y tipo de movimiento en [start, end)."""
        stmt = (
            select(
                InventoryMovement.item_id,
                InventoryMovementType.code,
                func.sum(InventoryMovement.quantity),
                func.sum(InventoryMovement.quantity * InventoryMovement.unit_cost),
                func.sum(case((InventoryMovement.unit_cost.is_(None), 1), else_=0)),
            )
            .join(InventoryMovementType, InventoryMovementType.id == InventoryMovement.movement_type_id)
            .where(InventoryMovement.occurred_at >= start, InventoryMovement.occurred_at < end)
            .group_by(InventoryMovement.item_id, InventoryMovementType.code)
        )
        return {
            (item_id, code): {"quantity": Decimal(qty), "value": value, "missing_cost": int(missing)}
            for item_id, code, qty, value, missing in self.session.execute(stmt)
        }


class InventoryPeriodRepository(Repository[InventoryPeriod]):
    model = InventoryPeriod

    def all_ordered(self) -> Sequence[InventoryPeriod]:
        return self.session.scalars(select(InventoryPeriod).order_by(InventoryPeriod.start_date.desc())).unique().all()

    def overlapping(self, start: date, end: date, exclude_id: int | None = None) -> InventoryPeriod | None:
        stmt = select(InventoryPeriod).where(InventoryPeriod.start_date <= end, InventoryPeriod.end_date >= start)
        if exclude_id is not None:
            stmt = stmt.where(InventoryPeriod.id != exclude_id)
        return self.session.scalars(stmt).first()

    def open_before(self, start: date) -> Sequence[InventoryPeriod]:
        stmt = select(InventoryPeriod).where(InventoryPeriod.status == "abierto", InventoryPeriod.end_date < start)
        return self.session.scalars(stmt.order_by(InventoryPeriod.start_date)).unique().all()

    def previous_closed(self, start: date) -> InventoryPeriod | None:
        stmt = (
            select(InventoryPeriod)
            .where(InventoryPeriod.status == "cerrado", InventoryPeriod.end_date < start)
            .order_by(InventoryPeriod.end_date.desc())
        )
        return self.session.scalars(stmt).first()

    def closed_containing(self, day: date) -> InventoryPeriod | None:
        stmt = select(InventoryPeriod).where(
            InventoryPeriod.status == "cerrado", InventoryPeriod.start_date <= day, InventoryPeriod.end_date >= day
        )
        return self.session.scalars(stmt).first()


class InventoryCountRepository(Repository[InventoryCount]):
    model = InventoryCount

    def by_period(self, period_id: int) -> dict[int, InventoryCount]:
        stmt = select(InventoryCount).where(InventoryCount.period_id == period_id)
        return {c.item_id: c for c in self.session.scalars(stmt).unique().all()}


class InventoryPeriodBalanceRepository(Repository[InventoryPeriodBalance]):
    model = InventoryPeriodBalance

    def by_period(self, period_id: int) -> dict[int, InventoryPeriodBalance]:
        stmt = select(InventoryPeriodBalance).where(InventoryPeriodBalance.period_id == period_id)
        return {b.item_id: b for b in self.session.scalars(stmt).unique().all()}


class MaintenanceRecordRepository(Repository[MaintenanceRecord]):
    model = MaintenanceRecord

    def search(
        self,
        *,
        offset: int,
        limit: int,
        device_id: int | None = None,
        sensor_id: int | None = None,
        maintenance_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        status: str | None = None,
        final_status: str | None = None,
        user_id: int | None = None,
        from_incident: bool | None = None,
    ) -> tuple[Sequence[MaintenanceRecord], int]:
        # Los mantenimientos en curso aún no tienen fecha de realización: se ordenan por su aceptación.
        when = func.coalesce(MaintenanceRecord.performed_at, MaintenanceRecord.accepted_at)
        stmt = select(MaintenanceRecord).order_by(when.desc(), MaintenanceRecord.id.desc())
        filters: list[Any] = []
        if status:
            filters.append(MaintenanceRecord.status == status)
        if final_status:
            filters.append(MaintenanceRecord.final_status == final_status)
        if user_id is not None:
            filters.append(MaintenanceRecord.user_id == user_id)
        if from_incident is not None:
            linked = MaintenanceRecord.incident_report_id.isnot(None)
            filters.append(linked if from_incident else MaintenanceRecord.incident_report_id.is_(None))
        if device_id is not None:
            filters.append(MaintenanceRecord.device_id == device_id)
        if sensor_id is not None:
            filters.append(MaintenanceRecord.sensor_id == sensor_id)
        if maintenance_type:
            filters.append(MaintenanceRecord.maintenance_type == maintenance_type)
        if date_from:
            filters.append(MaintenanceRecord.performed_at >= date_from)
        if date_to:
            filters.append(MaintenanceRecord.performed_at <= date_to)
        return self.paginate(stmt.where(*filters), offset=offset, limit=limit)


class MaintenanceItemRepository(Repository[MaintenanceItem]):
    model = MaintenanceItem
