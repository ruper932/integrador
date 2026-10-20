"""Normalización y coherencia de los datos personales (contexto boliviano).

El formato se valida en los esquemas de entrada; aquí se homogeneizan los valores para que
el mismo dato no se guarde de formas distintas (mayúsculas, espacios, correos) y se verifica
que la edad y los años de egreso sean posibles.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.core.errors import BusinessRuleError


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        value = " ".join(value.split())
        return value or None
    return value


def _name_case(value: str | None) -> str | None:
    # "MARÍA  del carmen" -> "María Del Carmen" (los nombres se muestran de forma uniforme).
    return " ".join(part.capitalize() for part in value.split()) if value else value


def normalize_profile(data: dict[str, Any]) -> dict[str, Any]:
    clean = {key: _clean(value) for key, value in data.items()}
    for key in ("first_names", "paternal_surname", "maternal_surname"):
        if key in clean:
            clean[key] = _name_case(clean[key])
    if clean.get("ci_complement"):
        clean["ci_complement"] = clean["ci_complement"].upper()
    for key in ("institutional_email", "personal_email"):
        if clean.get(key):
            clean[key] = clean[key].lower()
    return clean


def profile_changes(current: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """Nombres de los campos modificados (la auditoría no guarda los datos personales)."""
    return sorted(key for key, value in new.items() if current.get(key) != value)


# --- Edad y coherencia de la formación ---------------------------------------------

MIN_AGE = 18  # el sistema lo usa personal del CEA, mayor de edad
MAX_AGE = 100


def age_on(birth_date: date, today: date) -> int:
    """Años cumplidos a la fecha indicada."""
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))


def validate_birth_date(birth_date: date, today: date) -> None:
    if birth_date > today:
        raise BusinessRuleError("La fecha de nacimiento no puede ser futura.", code="fecha_nacimiento_invalida")
    age = age_on(birth_date, today)
    if age < MIN_AGE:
        raise BusinessRuleError(
            f"La persona debe ser mayor de edad (tener al menos {MIN_AGE} años); según la fecha indicada tiene {age}.",
            code="menor_de_edad",
        )
    if age > MAX_AGE:
        raise BusinessRuleError(
            f"La fecha de nacimiento indica {age} años; revise el dato.", code="fecha_nacimiento_invalida"
        )


@dataclass(frozen=True)
class DegreeTimeline:
    level_name: str
    min_graduation_age: int
    graduation_year: int | None


def validate_degree_ages(birth_date: date | None, degrees: Sequence[DegreeTimeline]) -> None:
    """El año de egreso debe ser posible para la edad de la persona y el nivel del título.

    La edad al egresar se calcula por año (año de egreso − año de nacimiento), por lo que la
    regla es tolerante con la fecha exacta de titulación dentro del año.
    """
    if birth_date is None:
        return  # perfiles anteriores sin fecha de nacimiento: no hay con qué comparar
    for degree in degrees:
        if degree.graduation_year is None:
            continue
        age_then = degree.graduation_year - birth_date.year
        if age_then < degree.min_graduation_age:
            earliest = birth_date.year + degree.min_graduation_age
            raise BusinessRuleError(
                f"El título de nivel «{degree.level_name}» no pudo obtenerse en {degree.graduation_year}: "
                f"la persona tenía {max(age_then, 0)} años y la edad mínima para ese nivel es "
                f"{degree.min_graduation_age} (año de egreso posible: {earliest} o posterior).",
                code="egreso_incoherente",
                details={"nivel": degree.level_name, "anio_minimo": earliest},
            )
