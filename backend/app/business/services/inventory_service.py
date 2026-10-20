"""Inventario de repuestos y componentes del hardware IoT."""

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.business.services.audit_service import AuditService
from app.business.services.context import RequestContext
from app.business.services.integrity import integrity_guard
from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.errors import BusinessRuleError, NotFoundError
from app.data.models.inventory import (
    InventoryCategory,
    InventoryItem,
    InventoryItemCompatibility,
    InventoryMovement,
    InventoryMovementType,
)
from app.data.repositories.inventory import (
    InventoryCategoryRepository,
    InventoryItemRepository,
    InventoryMovementRepository,
    InventoryMovementTypeRepository,
    InventoryPeriodRepository,
)
from app.data.repositories.iot import DeviceRepository, SensorRepository

MOVEMENT_IN = "entrada"
MOVEMENT_OUT = "salida"
MOVEMENT_MAINTENANCE_OUT = "salida_mantenimiento"
ADJUSTMENT_SURPLUS = "ajuste_sobrante"
ADJUSTMENT_SHORTAGE = "ajuste_faltante"


class InventoryService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.categories = InventoryCategoryRepository(session)
        self.items = InventoryItemRepository(session)
        self.movement_types = InventoryMovementTypeRepository(session)
        self.movements = InventoryMovementRepository(session)
        self.devices = DeviceRepository(session)
        self.sensors = SensorRepository(session)
        self.periods = InventoryPeriodRepository(session)
        self.audit = AuditService(session)
        self.tz = ZoneInfo(get_settings().local_timezone)

    # --- Categorías -------------------------------------------------------

    def list_categories(self, *, include_inactive: bool = False) -> Sequence[InventoryCategory]:
        return self.categories.list(
            limit=1000, order_by=InventoryCategory.name, is_active=None if include_inactive else True
        )

    def create_category(self, ctx: RequestContext, *, name: str, description: str | None) -> InventoryCategory:
        with integrity_guard(self.session, duplicate_message="Ya existe una categoría con ese nombre."):
            category = self.categories.add(InventoryCategory(name=name, description=description, is_active=True))
        self.audit.record(ctx, "inventario.categoria_crear", entity_type="inventory_category", entity_id=category.id)
        self.session.commit()
        return category

    def list_movement_types(self) -> Sequence[InventoryMovementType]:
        return self.movement_types.list(limit=100)

    # --- Repuestos --------------------------------------------------------

    def search_items(self, **filters: Any) -> tuple[Sequence[InventoryItem], int]:
        return self.items.search(**filters)

    def get_item(self, item_id: int) -> InventoryItem:
        item = self.items.get(item_id)
        if item is None:
            raise NotFoundError("Repuesto no encontrado.")
        return item

    def _check_category(self, category_id: int) -> None:
        category = self.categories.get(category_id)
        if category is None or not category.is_active:
            raise BusinessRuleError("La categoría indicada no existe o está inactiva.", code="categoria_invalida")

    def _set_compatibility(self, item: InventoryItem, device_ids: Sequence[int], sensor_ids: Sequence[int]) -> None:
        for device_id in set(device_ids):
            if self.devices.get(device_id) is None:
                raise BusinessRuleError(f"El dispositivo {device_id} no existe.", code="referencia_inexistente")
        for sensor_id in set(sensor_ids):
            if self.sensors.get(sensor_id) is None:
                raise BusinessRuleError(f"El sensor {sensor_id} no existe.", code="referencia_inexistente")
        item.compatibilities = [InventoryItemCompatibility(device_id=d) for d in sorted(set(device_ids))] + [
            InventoryItemCompatibility(sensor_id=s) for s in sorted(set(sensor_ids))
        ]

    def create_item(
        self,
        ctx: RequestContext,
        data: dict[str, Any],
        *,
        initial_stock: Decimal,
        device_ids: Sequence[int],
        sensor_ids: Sequence[int],
        initial_unit_cost: Decimal | None = None,
    ) -> InventoryItem:
        self._check_category(data["category_id"])
        with integrity_guard(self.session, duplicate_message="Ya existe un repuesto con ese código."):
            item = self.items.add(InventoryItem(current_stock=Decimal(0), is_active=True, **data))
        self._set_compatibility(item, device_ids, sensor_ids)
        self.audit.record(ctx, "inventario.repuesto_crear", entity_type="inventory_item", entity_id=item.id)
        if initial_stock > 0:
            self.apply_movement(
                ctx, item.id, MOVEMENT_IN, initial_stock, "Stock inicial", system=True, unit_cost=initial_unit_cost
            )
        self.session.commit()
        return item

    def update_item(
        self,
        ctx: RequestContext,
        item_id: int,
        data: dict[str, Any],
        *,
        device_ids: Sequence[int] | None,
        sensor_ids: Sequence[int] | None,
    ) -> InventoryItem:
        item = self.get_item(item_id)
        if "category_id" in data:
            self._check_category(data["category_id"])
        with integrity_guard(self.session, duplicate_message="Ya existe un repuesto con ese código."):
            for key, value in data.items():
                setattr(item, key, value)
        if device_ids is not None or sensor_ids is not None:
            current_devices = [c.device_id for c in item.compatibilities if c.device_id]
            current_sensors = [c.sensor_id for c in item.compatibilities if c.sensor_id]
            self._set_compatibility(
                item,
                device_ids if device_ids is not None else current_devices,
                sensor_ids if sensor_ids is not None else current_sensors,
            )
        self.audit.record(
            ctx,
            "inventario.repuesto_actualizar",
            entity_type="inventory_item",
            entity_id=item.id,
            details={k: str(v) for k, v in data.items()},
        )
        self.session.commit()
        return item

    def deactivate_item(self, ctx: RequestContext, item_id: int) -> InventoryItem:
        item = self.get_item(item_id)
        item.is_active = False
        self.audit.record(ctx, "inventario.repuesto_desactivar", entity_type="inventory_item", entity_id=item.id)
        self.session.commit()
        return item

    def low_stock(self) -> Sequence[InventoryItem]:
        return self.items.low_stock()

    def stock_report(
        self,
        *,
        include_inactive: bool,
        category_id: int | None = None,
        condition: str | None = None,
        low_stock_only: bool = False,
    ) -> Sequence[InventoryItem]:
        return self.items.all_for_report(
            include_inactive=include_inactive,
            category_id=category_id,
            condition=condition,
            low_stock_only=low_stock_only,
        )

    # --- Movimientos ------------------------------------------------------

    def register_movement(
        self,
        ctx: RequestContext,
        item_id: int,
        *,
        movement_type_code: str,
        quantity: Decimal,
        reason: str,
        unit_cost: Decimal | None = None,
    ) -> InventoryMovement:
        movement = self.apply_movement(ctx, item_id, movement_type_code, quantity, reason, unit_cost=unit_cost)
        self.session.commit()
        return movement

    def apply_movement(
        self,
        ctx: RequestContext,
        item_id: int,
        movement_type_code: str,
        quantity: Decimal,
        reason: str,
        *,
        system: bool = False,
        maintenance_record_id: int | None = None,
        unit_cost: Decimal | None = None,
        occurred_at: datetime | None = None,
        allow_inactive: bool = False,
    ) -> InventoryMovement:
        """Aplica un movimiento dentro de la transacción actual, con bloqueo de fila del repuesto.

        `occurred_at` (fecha efectiva) solo la fija el sistema, p. ej. en los ajustes de cierre;
        los movimientos manuales ocurren en el momento en que se registran.
        """
        if ctx.user_id is None:
            raise BusinessRuleError("Todo movimiento debe registrar el usuario responsable.", code="usuario_requerido")
        if quantity <= 0:
            raise BusinessRuleError("La cantidad debe ser mayor que cero.", code="cantidad_invalida")
        movement_type = self.movement_types.get_by_code(movement_type_code)
        if movement_type is None:
            raise BusinessRuleError("Tipo de movimiento inexistente.", code="tipo_movimiento_invalido")
        if not movement_type.manual_allowed and not system:
            raise BusinessRuleError(
                "Este tipo de movimiento lo genera el sistema (mantenimiento o cierre de periodo).",
                code="tipo_movimiento_no_manual",
            )
        if unit_cost is not None and (movement_type.direction < 0 or unit_cost < 0):
            raise BusinessRuleError(
                "El costo unitario solo se registra en entradas y no puede ser negativo.", code="costo_invalido"
            )
        effective_at = occurred_at or utcnow()
        closed = self.periods.closed_containing(effective_at.astimezone(self.tz).date())
        if closed is not None:
            raise BusinessRuleError(
                f"El periodo de inventario '{closed.name}' está cerrado; no admite movimientos.",
                code="periodo_cerrado",
            )
        item = self.items.get_for_update(item_id)
        if item is None:
            raise NotFoundError("Repuesto no encontrado.")
        if not item.is_active and not allow_inactive:
            raise BusinessRuleError(f"El repuesto '{item.code}' está desactivado.", code="repuesto_inactivo")

        stock_before = Decimal(item.current_stock)
        stock_after = stock_before + quantity * movement_type.direction
        if stock_after < 0:
            raise BusinessRuleError(
                f"Stock insuficiente para '{item.code}': disponible {stock_before.normalize()} {item.unit}, "
                f"solicitado {quantity.normalize()} {item.unit}.",
                code="stock_insuficiente",
                details={"item_id": item.id, "disponible": str(stock_before), "solicitado": str(quantity)},
            )
        item.current_stock = stock_after
        movement = self.movements.add(
            InventoryMovement(
                item_id=item.id,
                movement_type_id=movement_type.id,
                quantity=quantity,
                stock_before=stock_before,
                stock_after=stock_after,
                reason=reason,
                user_id=ctx.user_id,
                maintenance_record_id=maintenance_record_id,
                unit_cost=unit_cost,
                occurred_at=effective_at,
            )
        )
        self.audit.record(
            ctx,
            "inventario.movimiento",
            entity_type="inventory_item",
            entity_id=item.id,
            details={"tipo": movement_type.code, "cantidad": str(quantity), "stock_resultante": str(stock_after)},
        )
        return movement

    def search_movements(
        self,
        *,
        offset: int,
        limit: int,
        item_id: int | None = None,
        movement_type_code: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[Sequence[InventoryMovement], int]:
        if item_id is not None:
            self.get_item(item_id)
        return self.movements.search(
            offset=offset,
            limit=limit,
            item_id=item_id,
            movement_type_code=movement_type_code,
            date_from=date_from,
            date_to=date_to,
        )
