"""Datos personales y de formación de los usuarios (modelo normalizado).

- `users` conserva solo lo necesario para autenticarse; los datos personales viven en
  `user_profiles` (1:1), lo que permite restringir su acceso por separado.
- Instituciones, niveles académicos y cargos son catálogos (sin texto repetido).
- Un usuario puede registrar varios títulos (`user_degrees`, 1:N).
"""

from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.data.database import Base, TimestampMixin

# Departamentos de Bolivia (expedición del carnet de identidad).
CI_DEPARTMENTS = ("LP", "CB", "SC", "OR", "PT", "CH", "TJ", "BE", "PD")
INSTITUTION_TYPES = (
    "universidad_publica",
    "universidad_privada",
    "universidad_indigena",
    "escuela_formacion_maestros",
    "instituto_tecnico",
    "otra",
)


class AcademicLevel(Base):
    __tablename__ = "academic_levels"
    __table_args__ = (CheckConstraint("min_graduation_age BETWEEN 14 AND 60", name="min_graduation_age"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    # Edad mínima razonable para egresar con este nivel (valida el año de egreso frente a la edad).
    min_graduation_age: Mapped[int] = mapped_column(SmallInteger, default=16, server_default="16")


class Institution(Base, TimestampMixin):
    __tablename__ = "institutions"
    __table_args__ = (CheckConstraint(f"institution_type IN {INSTITUTION_TYPES}", name="institution_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    acronym: Mapped[str | None] = mapped_column(String(30))
    institution_type: Mapped[str] = mapped_column(String(40))
    city: Mapped[str | None] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Position(Base):
    """Cargo que la persona desempeña en el CEA."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"
    __table_args__ = (
        CheckConstraint(f"ci_issued_in IS NULL OR ci_issued_in IN {CI_DEPARTMENTS}", name="ci_issued_in"),
        CheckConstraint("mobile_phone IS NULL OR mobile_phone ~ '^[67][0-9]{7}$'", name="mobile_phone"),
        CheckConstraint("birth_date IS NULL OR birth_date >= DATE '1900-01-01'", name="birth_date"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    first_names: Mapped[str] = mapped_column(String(100))
    paternal_surname: Mapped[str | None] = mapped_column(String(60))
    maternal_surname: Mapped[str | None] = mapped_column(String(60))
    ci_number: Mapped[str | None] = mapped_column(String(12))
    ci_complement: Mapped[str | None] = mapped_column(String(4))
    ci_issued_in: Mapped[str | None] = mapped_column(String(2))
    institutional_email: Mapped[str | None] = mapped_column(String(120))
    personal_email: Mapped[str | None] = mapped_column(String(120))
    mobile_phone: Mapped[str | None] = mapped_column(String(8))
    # Opcional en la base solo por los perfiles anteriores; la API la exige al guardar.
    birth_date: Mapped[date | None] = mapped_column(Date)
    address: Mapped[str | None] = mapped_column(Text)
    position_id: Mapped[int | None] = mapped_column(ForeignKey("positions.id"))

    position: Mapped[Position | None] = relationship(lazy="joined")

    @property
    def full_name(self) -> str:
        parts = [self.first_names, self.paternal_surname, self.maternal_surname]
        return " ".join(p for p in parts if p)

    @property
    def is_complete(self) -> bool:
        return bool(
            self.first_names
            and (self.paternal_surname or self.maternal_surname)
            and self.ci_number
            and self.mobile_phone
            and self.birth_date
        )


# El CI (número + complemento) identifica a una persona; el complemento es opcional.
Index(
    "uq_user_profiles_ci",
    UserProfile.ci_number,
    func.coalesce(UserProfile.ci_complement, ""),
    unique=True,
    postgresql_where=UserProfile.ci_number.isnot(None),
)
Index(
    "uq_user_profiles_institutional_email",
    func.lower(UserProfile.institutional_email),
    unique=True,
    postgresql_where=UserProfile.institutional_email.isnot(None),
)


class UserDegree(Base, TimestampMixin):
    __tablename__ = "user_degrees"
    __table_args__ = (CheckConstraint("graduation_year BETWEEN 1950 AND 2100", name="graduation_year"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    academic_level_id: Mapped[int] = mapped_column(ForeignKey("academic_levels.id"))
    title: Mapped[str] = mapped_column(String(200))
    institution_id: Mapped[int] = mapped_column(ForeignKey("institutions.id"))
    graduation_year: Mapped[int | None] = mapped_column(SmallInteger)

    academic_level: Mapped[AcademicLevel] = relationship(lazy="joined")
    institution: Mapped[Institution] = relationship(lazy="joined")
