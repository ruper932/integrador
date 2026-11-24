"""Esquemas de datos personales, formación académica y catálogos."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.presentation.schemas.common import ORMModel

CiDepartment = Literal["LP", "CB", "SC", "OR", "PT", "CH", "TJ", "BE", "PD"]
InstitutionType = Literal[
    "universidad_publica",
    "universidad_privada",
    "universidad_indigena",
    "escuela_formacion_maestros",
    "instituto_tecnico",
    "otra",
]
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
# Letras, espacios, apóstrofo, punto o guion, con al menos una letra («   » o «--» no son nombres).
NAME_PATTERN = r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .-]*[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ' .-]*$"


class PersonalDataIn(BaseModel):
    """Datos personales que la propia persona puede actualizar (sin el cargo, que asigna el administrador)."""

    first_names: str = Field(min_length=2, max_length=100, pattern=NAME_PATTERN, description="Nombres")
    paternal_surname: str | None = Field(default=None, max_length=60, pattern=NAME_PATTERN)
    maternal_surname: str | None = Field(default=None, max_length=60, pattern=NAME_PATTERN)
    ci_number: str = Field(pattern=r"^\d{4,10}$", description="Número de carnet de identidad")
    ci_complement: str | None = Field(
        default=None, pattern=r"^[0-9A-Za-z]{1,2}$", description="Complemento del CI (p. ej. 1A), si existe"
    )
    ci_issued_in: CiDepartment | None = Field(default=None, description="Departamento de expedición")
    institutional_email: str | None = Field(default=None, max_length=120, pattern=EMAIL_PATTERN)
    personal_email: str | None = Field(default=None, max_length=120, pattern=EMAIL_PATTERN)
    mobile_phone: str = Field(pattern=r"^[67]\d{7}$", description="Celular de Bolivia (8 dígitos, inicia en 6 o 7)")
    birth_date: date = Field(description="Fecha de nacimiento (la persona debe tener al menos 18 años)")
    address: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def at_least_one_surname(self) -> "PersonalDataIn":
        if not ((self.paternal_surname or "").strip() or (self.maternal_surname or "").strip()):
            raise ValueError("Indique al menos un apellido (paterno o materno).")
        return self


class ProfileIn(PersonalDataIn):
    """Perfil completo que gestiona el administrador."""

    position_id: int | None = Field(default=None, description="Cargo en el CEA")


class PositionOut(ORMModel):
    id: int
    code: str
    name: str


class ProfileOut(ORMModel):
    first_names: str
    paternal_surname: str | None
    maternal_surname: str | None
    ci_number: str | None
    ci_complement: str | None
    ci_issued_in: str | None
    institutional_email: str | None
    personal_email: str | None
    mobile_phone: str | None
    birth_date: date | None
    address: str | None
    position: PositionOut | None


class DegreeIn(BaseModel):
    academic_level_id: int
    title: str = Field(min_length=3, max_length=200, description="Título obtenido")
    institution_id: int = Field(description="Institución de egreso")
    graduation_year: int | None = Field(default=None, ge=1950)

    @model_validator(mode="after")
    def year_not_in_future(self) -> "DegreeIn":
        if self.graduation_year and self.graduation_year > date.today().year:
            raise ValueError("El año de egreso no puede ser futuro.")
        return self


class AcademicLevelOut(ORMModel):
    id: int
    code: str
    name: str
    min_graduation_age: int


class InstitutionSummary(ORMModel):
    id: int
    name: str
    acronym: str | None


class DegreeOut(ORMModel):
    id: int
    title: str
    graduation_year: int | None
    academic_level: AcademicLevelOut
    institution: InstitutionSummary


class InstitutionIn(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    acronym: str | None = Field(default=None, max_length=30)
    institution_type: InstitutionType
    city: str | None = Field(default=None, max_length=80)


class InstitutionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=200)
    acronym: str | None = Field(default=None, max_length=30)
    institution_type: InstitutionType | None = None
    city: str | None = Field(default=None, max_length=80)
    is_active: bool | None = None


class InstitutionOut(ORMModel):
    id: int
    name: str
    acronym: str | None
    institution_type: str
    city: str | None
    is_active: bool


class OwnProfileUpdate(BaseModel):
    """Actualización del propio perfil (usuario autenticado)."""

    profile: PersonalDataIn
    degrees: list[DegreeIn] = Field(default_factory=list, max_length=20)
