"""Esquemas de solicitudes de reubicación de atrapanieblas."""

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.presentation.schemas.incidents import PersonOut
from app.presentation.schemas.iot import Orientation

RelocationStatus = Literal["pendiente", "aceptado", "en_progreso", "finalizado", "rechazado"]
RelocationScope = Literal["mine", "open", "assigned", "all"]
RelocationReason = Literal["espacio_insuficiente", "interferencia_con_actividades", "obstruccion_de_la_niebla", "otro"]

Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)]
Place = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=4000)]
RejectReason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=1000)]


class RelocationIn(BaseModel):
    fog_collector_id: int
    reason: RelocationReason
    description: Description = Field(description="Por qué el espacio actual ya no es adecuado")
    proposed_location_id: int | None = Field(default=None, description="Ubicación registrada que se sugiere")
    proposed_place: Place | None = Field(
        default=None, description="Lugar sugerido que aún no está registrado como ubicación"
    )

    @model_validator(mode="after")
    def one_proposal(self) -> Self:
        if self.proposed_location_id is not None and self.proposed_place is not None:
            raise ValueError("Indique una ubicación registrada o un lugar sugerido, no ambos.")
        return self


class RelocationFinishIn(BaseModel):
    destination_location_id: int
    new_orientation: Orientation | None = Field(default=None, description="Vacío para conservar la orientación")
    work_notes: Notes = Field(description="Trabajo realizado: desmontaje, traslado, anclaje, pruebas")


class RelocationRejectIn(BaseModel):
    reason: RejectReason


class PlaceOut(BaseModel):
    id: int
    name: str


class FogCollectorRefOut(BaseModel):
    id: int
    code: str
    name: str


class RelocationOut(BaseModel):
    id: int
    status: RelocationStatus
    reason: RelocationReason
    description: str
    fog_collector: FogCollectorRefOut
    origin_location: PlaceOut | None
    proposed_location: PlaceOut | None
    proposed_place: str | None
    destination_location: PlaceOut | None
    previous_orientation: str | None
    new_orientation: str | None
    work_notes: str | None
    rejection_reason: str | None
    requester: PersonOut
    assignee: PersonOut | None
    created_at: datetime
    accepted_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None


class RelocationSummaryOut(BaseModel):
    mine: dict[str, int] | None
    open: int | None
    assigned_active: int | None
    all: dict[str, int] | None
