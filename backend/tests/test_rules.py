"""Pruebas unitarias de reglas de negocio (sin base de datos)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.business.rules.measurements import ReadingRejected, assess_value, check_timestamp
from app.business.rules.passwords import validate_password_policy
from app.business.rules.people import DegreeTimeline, age_on, validate_birth_date, validate_degree_ages
from app.core.errors import BusinessRuleError
from app.core.security import generate_temporary_password, hash_password, verify_password
from app.data.models.iot import SensorType

HUMIDITY = SensorType(
    code="humedad_relativa", name="Humedad", unit="%", min_value=0, max_value=100, aggregation="instantaneo"
)


@pytest.mark.parametrize(
    ("value", "unit", "quality"),
    [
        (55.0, "%", "valida"),
        (0.0, "%", "valida"),
        (100.0, "%", "valida"),
        (None, "%", "sin_dato"),
        (100.1, "%", "fuera_de_rango"),
        (-0.1, "%", "fuera_de_rango"),
        (50.0, "pct", "unidad_invalida"),
        (float("nan"), "%", "invalida"),
    ],
)
def test_assess_value(value, unit, quality):
    assert assess_value(HUMIDITY, value, unit).quality == quality


def test_future_timestamp_is_rejected():
    now = datetime.now(UTC)
    check_timestamp(now + timedelta(seconds=60), now=now, max_future_skew=timedelta(minutes=5))
    with pytest.raises(ReadingRejected):
        check_timestamp(now + timedelta(minutes=10), now=now, max_future_skew=timedelta(minutes=5))


@pytest.mark.parametrize("password", ["corta1", "sololetrasaqui", "1234567890123", "juanperez2024x"])
def test_weak_passwords_are_rejected(password):
    with pytest.raises(BusinessRuleError):
        validate_password_policy(password, username="juanperez")


def test_strong_password_and_hashing():
    validate_password_policy("Atrapanieblas-2025", username="admin")
    hashed = hash_password("Atrapanieblas-2025")
    assert verify_password("Atrapanieblas-2025", hashed)
    assert not verify_password("otra-clave-1", hashed)
    assert hash_password("Atrapanieblas-2025") != hashed  # sal aleatoria


def test_temporary_password_meets_policy():
    for _ in range(20):
        validate_password_policy(generate_temporary_password(), username="usuario")


def test_age_counts_completed_years():
    assert age_on(date(2008, 10, 16), date(2026, 10, 15)) == 17
    assert age_on(date(2008, 10, 15), date(2026, 10, 15)) == 18
    assert age_on(date(2004, 2, 29), date(2026, 2, 28)) == 21


def test_birth_date_rules():
    today = date(2026, 10, 15)
    validate_birth_date(date(2008, 10, 15), today)
    with pytest.raises(BusinessRuleError) as minor:
        validate_birth_date(date(2008, 10, 16), today)
    assert minor.value.code == "menor_de_edad"
    with pytest.raises(BusinessRuleError):
        validate_birth_date(date(2027, 1, 1), today)


def test_degree_ages():
    birth = date(2006, 5, 1)
    validate_degree_ages(birth, [DegreeTimeline("Bachiller", 16, 2023), DegreeTimeline("Licenciatura", 21, None)])
    validate_degree_ages(None, [DegreeTimeline("Licenciatura", 21, 2010)])  # perfil anterior sin fecha
    with pytest.raises(BusinessRuleError) as error:
        validate_degree_ages(birth, [DegreeTimeline("Licenciatura", 21, 2024)])
    assert error.value.code == "egreso_incoherente"
    assert "18 años" in error.value.message
    with pytest.raises(BusinessRuleError):
        validate_degree_ages(birth, [DegreeTimeline("Bachiller", 16, 2001)])  # antes de nacer
