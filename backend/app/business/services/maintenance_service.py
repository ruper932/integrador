"""Registro de mantenimientos vinculados a dispositivos, sensores e inventario."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.business.services.audit_service import AuditService
from app.business.services.context import RequestContext
from app.business.services.inventory_service import MOVEMENT_MAINTENANCE_OUT, InventoryService
from app.core.clock import utcnow
from app.core.errors import BusinessRuleError, NotFoundError
from app.data.models.inventory import MAINTENANCE_FINISHED, MaintenanceItem, MaintenanceRecord
from app.data.repositories.inventory import MaintenanceItemRepository, MaintenanceRecordRepository
from app.data.repositories.iot import DeviceRepository, SensorRepository


@dataclass(frozen=True)
class UsedPart:
    item_id: int
    quantity: Decimal


class MaintenanceService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.records = MaintenanceRecordRepository(session)
        self.record_items = MaintenanceItemRepository(session)
        self.devices = DeviceRepository(session)
        self.sensors = SensorRepository(session)
        self.inventory = InventoryService(session)
        self.audit = AuditService(session)

    def search(self, **filters: object) -> tuple[Sequence[MaintenanceRecord], int]:
        return self.records.search(**filters)  # type: ignore[arg-type]

    def get(self, record_id: int) -> MaintenanceRecord:
        record = self.records.get(record_id)
        if record is None:
            raise NotFoundError("Mantenimiento no encontrado.")
        return record

    def validate_target(self, device_id: int, sensor_id: int | None) -> None:
        if self.devices.get(device_id) is None:
            raise BusinessRuleError("El dispositivo indicado no existe.", code="referencia_inexistente")
        if sensor_id is not None:
            sensor = self.sensors.get(sensor_id)
            if sensor is None or sensor.device_id != device_id:
                raise BusinessRuleError(
                    "El sensor indicado no existe o no pertenece al dispositivo.", code="sensor_no_asociado"
                )

    @staticmethod
    def validate_work(maintenance_type: str, parts: Sequence[UsedPart]) -> None:
        item_ids = [p.item_id for p in parts]
        if len(item_ids) != len(set(item_ids)):
            raise BusinessRuleError(
                "Un repuesto no puede repetirse en el mismo mantenimiento.", code="repuesto_repetido"
            )
        if maintenance_type == "reemplazo" and not parts:
            raise BusinessRuleError(
                "Un mantenimiento de reemplazo debe indicar los repuestos utilizados.", code="repuestos_requeridos"
            )

    def consume_parts(self, ctx: RequestContext, record: MaintenanceRecord, parts: Sequence[UsedPart]) -> None:
        """Registra los repuestos utilizados y su salida de inventario (falla si no hay stock)."""
        # Orden fijo de bloqueo para evitar interbloqueos entre transacciones concurrentes.
        for part in sorted(parts, key=lambda p: p.item_id):
            movement = self.inventory.apply_movement(
                ctx,
                part.item_id,
                MOVEMENT_MAINTENANCE_OUT,
                part.quantity,
                f"Mantenimiento #{record.id}",
                system=True,
                maintenance_record_id=record.id,
            )
            self.record_items.add(
                MaintenanceItem(
                    maintenance_record_id=record.id,
                    item_id=part.item_id,
                    quantity=part.quantity,
                    movement_id=movement.id,
                )
            )

    def register(
        self,
        ctx: RequestContext,
        *,
        device_id: int,
        sensor_id: int | None,
        performed_at: datetime,
        maintenance_type: str,
        description: str,
        final_status: str,
        parts: Sequence[UsedPart],
    ) -> MaintenanceRecord:
        """Registro directo de un mantenimiento ya realizado (sin reporte de incidencia)."""
        if ctx.user_id is None:
            raise BusinessRuleError("El mantenimiento debe tener un usuario responsable.", code="usuario_requerido")
        self.validate_target(device_id, sensor_id)
        if performed_at > utcnow() + timedelta(minutes=5):
            raise BusinessRuleError("La fecha del mantenimiento no puede estar en el futuro.", code="fecha_futura")
        self.validate_work(maintenance_type, parts)

        record = self.records.add(
            MaintenanceRecord(
                status=MAINTENANCE_FINISHED,
                device_id=device_id,
                sensor_id=sensor_id,
                performed_at=performed_at,
                finished_at=performed_at,
                user_id=ctx.user_id,
                maintenance_type=maintenance_type,
                description=description,
                final_status=final_status,
            )
        )
        self.consume_parts(ctx, record, parts)
        self.audit.record(
            ctx,
            "mantenimiento.registrar",
            entity_type="maintenance_record",
            entity_id=record.id,
            details={"device_id": device_id, "sensor_id": sensor_id, "repuestos": len(parts)},
        )
        self.session.commit()
        self.session.refresh(record)
        return record
