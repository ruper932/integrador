"""intervalo de muestreo por estación

- `devices.sample_interval_s`: segundos entre lecturas que debe usar la estación (5 «tiempo real», 30 o 60).
  Las estaciones existentes quedan en 60 s, el mismo valor que usaba el firmware.

Revision ID: 5b1e9c3d2a47
Revises: 106d673f7a40
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "5b1e9c3d2a47"
down_revision: str | Sequence[str] | None = "106d673f7a40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("sample_interval_s", sa.Integer(), server_default="60", nullable=False))
    op.create_check_constraint("sample_interval", "devices", "sample_interval_s IN (5, 30, 60)")


def downgrade() -> None:
    op.drop_constraint("ck_devices_sample_interval", "devices", type_="check")
    op.drop_column("devices", "sample_interval_s")
