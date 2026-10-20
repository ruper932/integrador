"""orientacion del atrapanieblas

Agrega `fog_collectors.orientation` (orientación de la malla), como en la versión anterior del
sistema. Columna opcional: no altera datos existentes.

Revision ID: dd5c474a8961
Revises: 4eca9300bd5f
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "dd5c474a8961"
down_revision: str | Sequence[str] | None = "4eca9300bd5f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("fog_collectors", sa.Column("orientation", sa.String(length=40), nullable=True))


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM fog_collectors WHERE orientation IS NOT NULL")):
        raise RuntimeError("Hay orientaciones registradas; revertir esta migración las eliminaría.")
    op.drop_column("fog_collectors", "orientation")
