"""Esquemas de inventario y mantenimiento."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, Field, computed_field

from app.presentation.schemas.common import ORMModel

CODE_PATTERN = r"^[A-Za-z0-9_.-]{2,40}$"
ItemCondition = Literal["nuevo", "usado", "reacondicionado", "en_revision", "danado"]
MaintenanceType = Literal["preventivo", "correctivo", "reemplazo", "calibracion", "limpieza", "inspeccion"]
FinalStatus = Literal["operativo", "operativo_con_observaciones", "fuera_de_servicio", "reemplazado"]


class CategoryIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=500)


class CategoryOut(ORMModel):
    id: int
    name: str
    description: str | None
    is_active: bool


class CompatibilityOut(ORMModel):
    device_id: int | None
    sensor_id: int | None


class ItemIn(BaseModel):
    code: str = Field(pattern=CODE_PATTERN)
    name: str = Field(min_length=2, max_length=150)
    description: str | None = None
    category_id: int
    unit: str = Field(min_length=1, max_length=20, description="Unidad de medida: unidad, metro, rollo, litro…")
    min_stock: Decimal = Field(default=Decimal(0), ge=0, max_digits=12, decimal_places=3)
    condition: ItemCondition = "nuevo"
    storage_location: str | None = Field(default=None, max_length=120)
    initial_stock: Decimal = Field(default=Decimal(0), ge=0, max_digits=12, decimal_places=3)
    initial_unit_cost: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=4, description="Costo unitario del stock inicial (Bs)"
    )
    compatible_device_ids: list[int] = Field(default_factory=list)
    compatible_sensor_ids: list[int] = Field(default_factory=list)


class ItemUpdate(BaseModel):
    code: str | None = Field(default=None, pattern=CODE_PATTERN)
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = None
    category_id: int | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    min_stock: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    condition: ItemCondition | None = None
    storage_location: str | None = Field(default=None, max_length=120)
    is_active: bool | None = None
    compatible_device_ids: list[int] | None = None
    compatible_sensor_ids: list[int] | None = None


class ItemOut(ORMModel):
    id: int
    code: str
    name: str
    description: str | None
    category: CategoryOut
    unit: str
    current_stock: Decimal
    min_stock: Decimal
    condition: str
    storage_location: str | None
    is_active: bool
    compatibilities: list[CompatibilityOut]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def low_stock(self) -> bool:
        return self.is_active and self.current_stock <= self.min_stock


class MovementIn(BaseModel):
    movement_type: Literal["entrada", "salida"]
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)
    reason: str = Field(min_length=3, max_length=255)
    unit_cost: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=4, description="Costo unitario en Bs (solo entradas)"
    )


class MovementTypeOut(ORMModel):
    code: str
    name: str
    direction: int


class MovementOut(ORMModel):
    id: int
    item_id: int
    movement_type: MovementTypeOut
    quantity: Decimal
    stock_before: Decimal
    stock_after: Decimal
    reason: str
    user_id: int
    username: str | None = None
    maintenance_record_id: int | None
    unit_cost: Decimal | None
    occurred_at: datetime
    created_at: datetime


class UsedPartIn(BaseModel):
    item_id: int
    quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=3)


class MaintenanceIn(BaseModel):
    device_id: int
    sensor_id: int | None = None
    performed_at: AwareDatetime
    maintenance_type: MaintenanceType
    description: str = Field(min_length=5, max_length=4000)
    final_status: FinalStatus
    parts: list[UsedPartIn] = Field(default_factory=list)


class MaintenanceItemOut(ORMModel):
    item_id: int
    item_code: str
    item_name: str
    quantity: Decimal
    movement_id: int


MaintenanceStatus = Literal["aceptado", "en_progreso", "finalizado"]


class MaintenanceOut(ORMModel):
    id: int
    status: MaintenanceStatus
    incident_report_id: int | None
    # Mientras el mantenimiento no esté finalizado, los detalles del trabajo pueden estar vacíos.
    device_id: int | None
    device_code: str | None
    sensor_id: int | None
    sensor_code: str | None
    performed_at: datetime | None
    user_id: int
    username: str
    user_full_name: str
    maintenance_type: MaintenanceType | None
    description: str | None
    final_status: FinalStatus | None
    accepted_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    items: list[MaintenanceItemOut]


# --- Inventario periódico ------------------------------------------------------


class PeriodIn(BaseModel):
    name: str = Field(min_length=3, max_length=80, description="Ej.: Octubre 2026 o Gestión 2026")
    start_date: date
    end_date: date
    notes: str | None = Field(default=None, max_length=1000)


class PeriodOut(ORMModel):
    id: int
    name: str
    start_date: date
    end_date: date
    status: str
    notes: str | None
    created_at: datetime
    closed_at: datetime | None
    closed_by_id: int | None


class CountIn(BaseModel):
    item_id: int
    counted_quantity: Decimal = Field(ge=0, max_digits=12, decimal_places=3)
    notes: str | None = Field(default=None, max_length=255)


class CountsIn(BaseModel):
    counts: list[CountIn] = Field(min_length=1, max_length=5000)


class ItemSummaryOut(ORMModel):
    id: int
    code: str
    name: str
    unit: str
    is_active: bool


class BalanceOut(BaseModel):
    item: ItemSummaryOut
    opening_quantity: Decimal
    entries_quantity: Decimal
    exits_quantity: Decimal
    maintenance_exits_quantity: Decimal
    adjustments_quantity: Decimal
    theoretical_quantity: Decimal
    counted_quantity: Decimal | None
    difference: Decimal | None
    closing_quantity: Decimal
    opening_value: Decimal | None
    entries_value: Decimal | None
    average_unit_cost: Decimal | None
    closing_value: Decimal | None


class PeriodSummaryOut(BaseModel):
    period: PeriodOut
    provisional: bool = Field(description="True mientras el periodo esté abierto (saldos no congelados)")
    counted_items: int
    pending_count_items: int
    total_value: Decimal | None = Field(description="Null si algún repuesto no tiene costo conocido")
    balances: list[BalanceOut]
