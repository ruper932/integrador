"""Esquemas de reportes de incidencia y notificaciones."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from app.presentation.schemas.common import ORMModel
from app.presentation.schemas.inventory import FinalStatus, MaintenanceOut, MaintenanceType, UsedPartIn

Priority = Literal["baja", "media", "alta"]
IncidentStatus = Literal["abierto", "aceptado", "en_progreso", "finalizado"]
IncidentScope = Literal["mine", "open", "assigned", "all"]

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=120)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)]
Location = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
WorkDescription = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=4000)]


class IncidentIn(BaseModel):
    title: Title = Field(description="Resumen breve de la situación")
    description: Description
    priority: Priority = "media"
    location_reference: Location | None = Field(
        default=None, description="Referencia del lugar, p. ej. «atrapanieblas norte, junto al tanque»"
    )
    device_id: int | None = None
    sensor_id: int | None = None


class IncidentFinishIn(BaseModel):
    """Detalle del trabajo realizado. Si no se indica el dispositivo, se usa el del reporte."""

    device_id: int | None = None
    sensor_id: int | None = None
    maintenance_type: MaintenanceType
    description: WorkDescription
    final_status: FinalStatus
    parts: list[UsedPartIn] = Field(default_factory=list)


class PersonOut(BaseModel):
    id: int
    username: str
    full_name: str


class IncidentOut(BaseModel):
    id: int
    title: str
    description: str
    priority: Priority
    location_reference: str | None
    status: IncidentStatus
    device_id: int | None
    device_code: str | None
    device_name: str | None
    sensor_id: int | None
    sensor_code: str | None
    reporter: PersonOut
    assignee: PersonOut | None
    created_at: datetime
    maintenance: MaintenanceOut | None


class IncidentSummaryOut(BaseModel):
    mine: dict[str, int] | None
    open: int | None
    assigned_active: int | None
    all: dict[str, int] | None


class NotificationOut(ORMModel):
    id: int
    title: str
    message: str
    incident_report_id: int | None
    created_at: datetime
    read_at: datetime | None


class NotificationsOut(BaseModel):
    items: list[NotificationOut]
    unread: int
