"""fecha de nacimiento y edad minima de egreso

- `user_profiles.birth_date`: la API la exige (persona mayor de 18 años); en la base admite NULL
  solo para los perfiles registrados antes de este cambio.
- `academic_levels.min_graduation_age`: edad mínima razonable para egresar en cada nivel, con la
  que se valida que el año de egreso sea coherente con la edad. Valores iniciales según la
  duración habitual de los estudios en Bolivia (bachillerato a los 17–18 años, licenciatura y
  formación de maestros de 5 años, posgrados después de la licenciatura); la institución puede
  ajustarlos.

Revision ID: 4eca9300bd5f
Revises: ab5f416fb049
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4eca9300bd5f"
down_revision: str | Sequence[str] | None = "ab5f416fb049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MIN_GRADUATION_AGES = {
    "bachiller": 16,
    "tecnico_auxiliar": 17,
    "tecnico_medio": 18,
    "tecnico_superior": 19,
    "maestro_normalista": 21,
    "licenciatura": 21,
    "diplomado": 22,
    "especialidad": 22,
    "maestria": 23,
    "doctorado": 25,
}


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("birth_date", sa.Date(), nullable=True))
    op.create_check_constraint("birth_date", "user_profiles", "birth_date IS NULL OR birth_date >= DATE '1900-01-01'")
    op.add_column(
        "academic_levels",
        sa.Column("min_graduation_age", sa.SmallInteger(), server_default="16", nullable=False),
    )
    op.create_check_constraint("min_graduation_age", "academic_levels", "min_graduation_age BETWEEN 14 AND 60")
    conn = op.get_bind()
    for code, age in MIN_GRADUATION_AGES.items():
        conn.execute(
            sa.text("UPDATE academic_levels SET min_graduation_age = :age WHERE code = :code"),
            {"age": age, "code": code},
        )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM user_profiles WHERE birth_date IS NOT NULL")):
        raise RuntimeError("Hay fechas de nacimiento registradas; revertir esta migración las eliminaría.")
    op.drop_constraint(op.f("ck_academic_levels_min_graduation_age"), "academic_levels", type_="check")
    op.drop_column("academic_levels", "min_graduation_age")
    op.drop_constraint(op.f("ck_user_profiles_birth_date"), "user_profiles", type_="check")
    op.drop_column("user_profiles", "birth_date")
