"""carga de firmware

- `firmware_releases`: imágenes `firmware.bin` cargadas para actualizar las estaciones por OTA. La
  imagen se guarda en la base para que entre en los respaldos de PostgreSQL.
- `devices.target_firmware_id`: versión que cada estación debe instalar (vacío: ninguna).
- Permiso `firmware.gestionar` para el administrador y el personal de mantenimiento.

El downgrade se niega si ya hay versiones cargadas, para no perderlas.

Revision ID: 106d673f7a40
Revises: c41f2a7d9e10
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "106d673f7a40"
down_revision: str | Sequence[str] | None = "c41f2a7d9e10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSION = ("firmware.gestionar", "Cargar versiones de firmware y asignarlas a las estaciones ESP32")
ROLES = ("administrador", "mantenimiento")


def upgrade() -> None:
    op.create_table(
        "firmware_releases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("md5", sa.String(length=32), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"], ["users.id"], name=op.f("fk_firmware_releases_uploaded_by_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_firmware_releases")),
        sa.UniqueConstraint("version", name=op.f("uq_firmware_releases_version")),
    )
    op.add_column("devices", sa.Column("target_firmware_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_devices_target_firmware_id_firmware_releases"),
        "devices",
        "firmware_releases",
        ["target_firmware_id"],
        ["id"],
    )

    conn = op.get_bind()
    conn.execute(
        sa.text("INSERT INTO permissions (code, description) VALUES (:code, :description)"),
        {"code": PERMISSION[0], "description": PERMISSION[1]},
    )
    conn.execute(
        sa.text(
            "INSERT INTO role_permissions (role_id, permission_id) "
            "SELECT r.id, p.id FROM roles r, permissions p WHERE r.name = ANY(:roles) AND p.code = :code"
        ),
        {"roles": list(ROLES), "code": PERMISSION[0]},
    )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.scalar(sa.text("SELECT count(*) FROM firmware_releases")):
        raise RuntimeError("Hay versiones de firmware cargadas; revertir esta migración las eliminaría.")
    conn.execute(
        sa.text("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = :code)"),
        {"code": PERMISSION[0]},
    )
    conn.execute(sa.text("DELETE FROM permissions WHERE code = :code"), {"code": PERMISSION[0]})
    op.drop_constraint(op.f("fk_devices_target_firmware_id_firmware_releases"), "devices", type_="foreignkey")
    op.drop_column("devices", "target_firmware_id")
    op.drop_table("firmware_releases")
