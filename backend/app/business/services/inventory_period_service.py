"""Sistema de inventario periódico.

Ciclo de cada periodo (mes, trimestre o gestión):
1. Se abre el periodo con fechas que no se superponen con otros.
2. Durante el periodo se registran entradas y salidas (el control de stock disponible se
   mantiene, porque no se permite retirar más de lo disponible).
3. Al final se realiza el conteo físico de cada repuesto.
4. Al cerrar, el sistema compara lo contado con el saldo según registros, genera ajustes por
   sobrantes o faltantes (fechados al final del periodo), congela los saldos y valoriza el
   inventario por costo promedio ponderado. Un periodo cerrado no admite más movimientos.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.business.services.audit_service import AuditService
from app.business.services.context import RequestContext
from app.business.services.integrity import integrity_guard
from app.business.services.inventory_service import (
    ADJUSTMENT_SHORTAGE,
    ADJUSTMENT_SURPLUS,
    MOVEMENT_IN,
    MOVEMENT_MAINTENANCE_OUT,
    MOVEMENT_OUT,
    InventoryService,
)
from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.errors import BusinessRuleError, NotFoundError
from app.data.models.inventory import InventoryCount, InventoryItem, InventoryPeriod, InventoryPeriodBalance
from app.data.repositories.inventory import (
    InventoryCountRepository,
    InventoryItemRepository,
    InventoryMovementRepository,
    InventoryPeriodBalanceRepository,
    InventoryPeriodRepository,
)

ZERO = Decimal(0)
QTY = Decimal("0.001")
MONEY = Decimal("0.01")
UNIT_COST = Decimal("0.0001")


@dataclass
class ItemBalance:
    """Resumen de un repuesto en un periodo (provisional si el periodo sigue abierto)."""

    item: InventoryItem
    opening_quantity: Decimal
    entries_quantity: Decimal
    exits_quantity: Decimal
    maintenance_exits_quantity: Decimal
    adjustments_quantity: Decimal
    theoretical_quantity: Decimal
    counted_quantity: Decimal | None
    closing_quantity: Decimal
    opening_value: Decimal | None
    entries_value: Decimal | None
    average_unit_cost: Decimal | None
    closing_value: Decimal | None

    @property
    def difference(self) -> Decimal | None:
        if self.counted_quantity is None:
            return None
        return self.counted_quantity - self.theoretical_quantity


@dataclass(frozen=True)
class PeriodSummary:
    period: InventoryPeriod
    provisional: bool
    balances: list[ItemBalance]

    @property
    def total_value(self) -> Decimal | None:
        values = [b.closing_value for b in self.balances]
        return None if any(v is None for v in values) else sum(values, ZERO)


class InventoryPeriodService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.periods = InventoryPeriodRepository(session)
        self.counts = InventoryCountRepository(session)
        self.balances = InventoryPeriodBalanceRepository(session)
        self.items = InventoryItemRepository(session)
        self.movements = InventoryMovementRepository(session)
        self.inventory = InventoryService(session)
        self.audit = AuditService(session)
        self.tz = ZoneInfo(get_settings().local_timezone)

    # --- Fechas -----------------------------------------------------------------

    def boundaries(self, period: InventoryPeriod) -> tuple[datetime, datetime]:
        """Inicio y fin [start, end) del periodo en hora de Bolivia."""
        start = datetime.combine(period.start_date, time.min, tzinfo=self.tz)
        end = datetime.combine(period.end_date + timedelta(days=1), time.min, tzinfo=self.tz)
        return start, end

    def _today(self) -> date:
        return utcnow().astimezone(self.tz).date()

    # --- Periodos ---------------------------------------------------------------

    def list(self) -> Sequence[InventoryPeriod]:
        return self.periods.all_ordered()

    def get(self, period_id: int) -> InventoryPeriod:
        period = self.periods.get(period_id)
        if period is None:
            raise NotFoundError("Periodo de inventario no encontrado.")
        return period

    def create(
        self, ctx: RequestContext, *, name: str, start_date: date, end_date: date, notes: str | None
    ) -> InventoryPeriod:
        if start_date > end_date:
            raise BusinessRuleError("La fecha inicial debe ser anterior o igual a la final.", code="rango_invalido")
        overlap = self.periods.overlapping(start_date, end_date)
        if overlap is not None:
            raise BusinessRuleError(
                f"Las fechas se superponen con el periodo '{overlap.name}'.", code="periodo_superpuesto"
            )
        with integrity_guard(self.session, duplicate_message="Ya existe un periodo con ese nombre."):
            period = self.periods.add(
                InventoryPeriod(
                    name=" ".join(name.split()),
                    start_date=start_date,
                    end_date=end_date,
                    status="abierto",
                    notes=notes,
                    created_by_id=ctx.user_id,
                )
            )
        self.audit.record(
            ctx,
            "inventario.periodo_crear",
            entity_type="inventory_period",
            entity_id=period.id,
            details={"inicio": str(start_date), "fin": str(end_date)},
        )
        self.session.commit()
        return period

    # --- Conteo físico ------------------------------------------------------------

    def _items_in_scope(self, period: InventoryPeriod, counts: dict[int, InventoryCount]) -> list[InventoryItem]:
        """Repuestos con movimientos hasta el final del periodo, más los que tienen conteo físico."""
        _, end = self.boundaries(period)
        with_history = self.movements.item_ids_with_movements_before(end)
        items = self.items.list(limit=100_000, order_by=InventoryItem.code)
        return [i for i in items if i.id in with_history or i.id in counts]

    def register_counts(
        self, ctx: RequestContext, period_id: int, entries: Sequence[dict[str, Any]]
    ) -> dict[int, InventoryCount]:
        period = self.get(period_id)
        if period.status != "abierto":
            raise BusinessRuleError("El periodo está cerrado; no admite conteos.", code="periodo_cerrado")
        counts = self.counts.by_period(period.id)
        for entry in entries:
            item = self.items.get(entry["item_id"])
            if item is None:
                raise BusinessRuleError(f"El repuesto {entry['item_id']} no existe.", code="referencia_inexistente")
            quantity = Decimal(entry["counted_quantity"])
            if quantity < 0:
                raise BusinessRuleError("La cantidad contada no puede ser negativa.", code="cantidad_invalida")
            count = counts.get(item.id)
            if count is None:
                count = self.counts.add(
                    InventoryCount(
                        period_id=period.id,
                        item_id=item.id,
                        counted_quantity=quantity,
                        notes=entry.get("notes"),
                        counted_by_id=ctx.user_id,
                    )
                )
                counts[item.id] = count
            else:
                count.counted_quantity = quantity
                count.notes = entry.get("notes")
                count.counted_by_id = ctx.user_id
                count.counted_at = utcnow()
        self.audit.record(
            ctx,
            "inventario.conteo_registrar",
            entity_type="inventory_period",
            entity_id=period.id,
            details={"repuestos": len(entries)},
        )
        self.session.commit()
        return counts

    # --- Cálculo de saldos ----------------------------------------------------------

    def _previous_values(self, period: InventoryPeriod) -> dict[int, InventoryPeriodBalance]:
        previous = self.periods.previous_closed(period.start_date)
        return self.balances.by_period(previous.id) if previous else {}

    def _compute(
        self, period: InventoryPeriod, items: list[InventoryItem], counts: dict[int, InventoryCount]
    ) -> list[ItemBalance]:
        start, end = self.boundaries(period)
        ids = [i.id for i in items]
        opening = self.movements.balances_before(start, ids)
        totals = self.movements.totals_between(start, end)
        previous = self._previous_values(period)

        result: list[ItemBalance] = []
        for item in items:

            def qty(code: str, item_id: int = item.id) -> Decimal:
                return totals.get((item_id, code), {}).get("quantity", ZERO)

            open_qty = opening.get(item.id, ZERO)
            entries = qty(MOVEMENT_IN)
            exits = qty(MOVEMENT_OUT)
            maintenance = qty(MOVEMENT_MAINTENANCE_OUT)
            adjustments = qty(ADJUSTMENT_SURPLUS) - qty(ADJUSTMENT_SHORTAGE)
            theoretical = open_qty + entries - exits - maintenance + adjustments
            count = counts.get(item.id)
            counted = Decimal(count.counted_quantity) if count else None
            closing = counted if counted is not None else theoretical

            # Valorización por costo promedio ponderado del periodo.
            prev = previous.get(item.id)
            if prev is not None and prev.closing_value is not None:
                opening_value: Decimal | None = Decimal(prev.closing_value)
            elif open_qty == 0:
                opening_value = ZERO
            else:
                opening_value = None  # existencias iniciales sin costo conocido
            entry_totals = totals.get((item.id, MOVEMENT_IN))
            if entry_totals is None:
                entries_value: Decimal | None = ZERO
            elif entry_totals["missing_cost"]:
                entries_value = None  # alguna entrada sin costo unitario
            else:
                entries_value = Decimal(entry_totals["value"] or 0)

            average: Decimal | None = None
            if opening_value is not None and entries_value is not None:
                base_qty = open_qty + entries
                if base_qty > 0:
                    average = ((opening_value + entries_value) / base_qty).quantize(UNIT_COST, ROUND_HALF_UP)
                elif prev is not None and prev.average_unit_cost is not None:
                    average = Decimal(prev.average_unit_cost)
            closing_value = (closing * average).quantize(MONEY, ROUND_HALF_UP) if average is not None else None
            if closing == 0:
                closing_value = ZERO

            result.append(
                ItemBalance(
                    item=item,
                    opening_quantity=open_qty,
                    entries_quantity=entries,
                    exits_quantity=exits,
                    maintenance_exits_quantity=maintenance,
                    adjustments_quantity=adjustments,
                    theoretical_quantity=theoretical,
                    counted_quantity=counted,
                    closing_quantity=closing,
                    opening_value=opening_value.quantize(MONEY) if opening_value is not None else None,
                    entries_value=entries_value.quantize(MONEY) if entries_value is not None else None,
                    average_unit_cost=average,
                    closing_value=closing_value,
                )
            )
        return result

    def summary(self, period_id: int) -> PeriodSummary:
        """Saldos del periodo: congelados si está cerrado, provisionales si sigue abierto."""
        period = self.get(period_id)
        if period.status == "cerrado":
            counts = self.counts.by_period(period.id)
            balances = []
            for b in sorted(self.balances.by_period(period.id).values(), key=lambda x: x.item.code):
                count = counts.get(b.item_id)
                balances.append(
                    ItemBalance(
                        item=b.item,
                        opening_quantity=b.opening_quantity,
                        entries_quantity=b.entries_quantity,
                        exits_quantity=b.exits_quantity,
                        maintenance_exits_quantity=b.maintenance_exits_quantity,
                        adjustments_quantity=b.adjustments_quantity,
                        theoretical_quantity=(
                            count.theoretical_quantity
                            if count and count.theoretical_quantity is not None
                            else b.closing_quantity
                        ),
                        counted_quantity=count.counted_quantity if count else None,
                        closing_quantity=b.closing_quantity,
                        opening_value=b.opening_value,
                        entries_value=b.entries_value,
                        average_unit_cost=b.average_unit_cost,
                        closing_value=b.closing_value,
                    )
                )
            return PeriodSummary(period=period, provisional=False, balances=balances)
        counts = self.counts.by_period(period.id)
        items = self._items_in_scope(period, counts)
        return PeriodSummary(period=period, provisional=True, balances=self._compute(period, items, counts))

    # --- Cierre ---------------------------------------------------------------------

    def close(self, ctx: RequestContext, period_id: int) -> PeriodSummary:
        period = self.periods.get_for_update(period_id)
        if period is None:
            raise NotFoundError("Periodo de inventario no encontrado.")
        if period.status != "abierto":
            raise BusinessRuleError("El periodo ya está cerrado.", code="periodo_cerrado")
        if period.end_date >= self._today():
            raise BusinessRuleError(
                "Solo se puede cerrar un periodo que ya terminó (después de su fecha final).",
                code="periodo_en_curso",
            )
        pending = self.periods.open_before(period.start_date)
        if pending:
            raise BusinessRuleError(
                f"Primero debe cerrar el periodo anterior '{pending[0].name}'.", code="periodo_anterior_abierto"
            )

        counts = self.counts.by_period(period.id)
        items = self._items_in_scope(period, counts)
        missing = [i.code for i in items if i.is_active and i.id not in counts]
        if missing:
            raise BusinessRuleError(
                "Falta el conteo físico de: " + ", ".join(missing[:20]) + ("…" if len(missing) > 20 else ""),
                code="conteo_incompleto",
                details={"faltantes": missing},
            )

        # Bloqueo de los repuestos en orden fijo para que no cambien durante el cierre.
        for item in sorted(items, key=lambda i: i.id):
            self.items.get_for_update(item.id)

        _, end = self.boundaries(period)
        adjustment_time = end - timedelta(microseconds=1)  # el ajuste pertenece al periodo
        computed = self._compute(period, items, counts)
        for balance in computed:
            diff = balance.difference
            if diff:
                code = ADJUSTMENT_SURPLUS if diff > 0 else ADJUSTMENT_SHORTAGE
                self.inventory.apply_movement(
                    ctx,
                    balance.item.id,
                    code,
                    abs(diff),
                    f"Ajuste por conteo físico — {period.name}",
                    system=True,
                    occurred_at=adjustment_time,
                    allow_inactive=True,
                )
            count = counts.get(balance.item.id)
            if count is not None:
                count.theoretical_quantity = balance.theoretical_quantity
                count.difference = diff
            self.balances.add(
                InventoryPeriodBalance(
                    period_id=period.id,
                    item_id=balance.item.id,
                    opening_quantity=balance.opening_quantity,
                    entries_quantity=balance.entries_quantity,
                    exits_quantity=balance.exits_quantity,
                    maintenance_exits_quantity=balance.maintenance_exits_quantity,
                    adjustments_quantity=balance.adjustments_quantity + (diff or ZERO),
                    closing_quantity=balance.closing_quantity,
                    opening_value=balance.opening_value,
                    entries_value=balance.entries_value,
                    average_unit_cost=balance.average_unit_cost,
                    closing_value=balance.closing_value,
                )
            )
        period.status = "cerrado"
        period.closed_at = utcnow()
        period.closed_by_id = ctx.user_id
        adjusted = [b.item.code for b in computed if b.difference]
        self.audit.record(
            ctx,
            "inventario.periodo_cerrar",
            entity_type="inventory_period",
            entity_id=period.id,
            details={"repuestos": len(computed), "ajustados": adjusted},
        )
        self.session.commit()
        return self.summary(period.id)
