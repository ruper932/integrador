"""reubicacion de atrapanieblas

- `fog_collector_relocations`: un docente solicita reubicar un atrapanieblas (p. ej. por falta de
  espacio) y el personal de mantenimiento la acepta, la ejecuta y la finaliza con la nueva ubicación,
  o la rechaza indicando el motivo. Un índice único parcial impide dos solicitudes en curso para el
  mismo atrapanieblas.
- `notifications.relocation_id`: los avisos del proceso enlazan con la solicitud.
- Permisos `reubicaciones.solicitar`, `reubicaciones.atender` y `reubicaciones.supervisar`.

El downgrade no elimina información: se niega a continuar si ya existen solicitudes.
Conserva el permiso de consulta de infraestructura del rol de mantenimiento.

Revision ID: c41f2a7d9e10
Revises: 7b3e9c1d2a40
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c41f2a7d9e10"
down_revision: str | Sequence[str] | None = "7b3e9c1d2a40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_PERMISSIONS = {
    "reubicaciones.solicitar": "Solicitar la reubicación de un atrapanieblas y seguir la solicitud",
    "reubicaciones.atender": "Aceptar, ejecutar y finalizar o rechazar reubicaciones de atrapanieblas",
    "reubicaciones.supervisar": "Consultar todas las solicitudes de reubicación",
}
GRANTS = {
    "administrador": list(NEW_PERMISSIONS),
    "director": ["reubicaciones.solicitar", "reubicaciones.supervisar"],
    "docente": ["reubicaciones.solicitar"],
    # El personal de mantenimiento elige la ubicación de destino: necesita consultar la infraestructura.
    "mantenimiento": ["reubicaciones.atender", "infraestructura.consultar"],
}


def upgrade() -> None:
    op.create_table(
        "fog_collector_relocations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fog_collector_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=30), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("origin_location_id", sa.Integer(), nullable=True),
        sa.Column("proposed_location_id", sa.Integer(), nullable=True),
        sa.Column("proposed_place", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=15), server_default="pendiente", nullable=False),
        sa.Column("assigned_to_id", sa.Integer(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("destination_location_id", sa.Integer(), nullable=True),
        sa.Column("previous_orientation", sa.String(length=40), nullable=True),
        sa.Column("new_orientation", sa.String(length=40), nullable=True),
        sa.Column("work_notes", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('pendiente', 'aceptado', 'en_progreso', 'finalizado', 'rechazado')",
            name=op.f("ck_fog_collector_relocations_status"),
        ),
        sa.CheckConstraint(
            "reason IN ('espacio_insuficiente', 'interferencia_con_actividades', 'obstruccion_de_la_niebla', 'otro')",
            name=op.f("ck_fog_collector_relocations_reason"),
        ),
        sa.CheckConstraint(
            "status = 'pendiente' OR status = 'rechazado' OR assigned_to_id IS NOT NULL",
            name=op.f("ck_fog_collector_relocations_asignada"),
        ),
        sa.CheckConstraint(
            "status <> 'finalizado' OR (destination_location_id IS NOT NULL AND work_notes IS NOT NULL"
            " AND finished_at IS NOT NULL)",
            name=op.f("ck_fog_collector_relocations_finalizada_completa"),
        ),
        sa.CheckConstraint(
            "status <> 'rechazado' OR rejection_reason IS NOT NULL",
            name=op.f("ck_fog_collector_relocations_rechazo_motivado"),
        ),
        sa.ForeignKeyConstraint(
            ["fog_collector_id"],
            ["fog_collectors.id"],
            name=op.f("fk_fog_collector_relocations_fog_collector_id_fog_collectors"),
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_id"], ["users.id"], name=op.f("fk_fog_collector_relocations_requested_by_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to_id"], ["users.id"], name=op.f("fk_fog_collector_relocations_assigned_to_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["origin_location_id"],
            ["locations.id"],
            name=op.f("fk_fog_collector_relocations_origin_location_id_locations"),
        ),
        sa.ForeignKeyConstraint(
            ["proposed_location_id"],
            ["locations.id"],
            name=op.f("fk_fog_collector_relocations_proposed_location_id_locations"),
        ),
        sa.ForeignKeyConstraint(
            ["destination_location_id"],
            ["locations.id"],
            name=op.f("fk_fog_collector_relocations_destination_location_id_locations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fog_collector_relocations")),
    )
    for column in ("fog_collector_id", "requested_by_id", "assigned_to_id"):
        op.create_index(
            op.f(f"ix_fog_collector_relocations_{column}"), "fog_collector_relocations", [column], unique=False
        )
    op.create_index(
        "uq_fog_collector_relocations_activa",
        "fog_collector_relocations",
        ["fog_collector_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pendiente', 'aceptado', 'en_progreso')"),
    )

    op.add_column("notifications", sa.Column("relocation_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_notifications_relocation_id_fog_collector_relocations"),
        "notifications",
        "fog_collector_relocations",
        ["relocation_id"],
        ["id"],
    )

    conn = op.get_bind()
    permissions = sa.table("permissions", sa.column("code"), sa.column("description"))
    op.bulk_insert(permissions, [{"code": c, "description": d} for c, d in NEW_PERMISSIONS.items()])
    for role, codes in GRANTS.items():
        conn.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT r.id, p.id FROM roles r, permissions p "
                "WHERE r.name = :role AND p.code = ANY(:codes) "
                "AND NOT EXISTS (SELECT 1 FROM role_permissions rp WHERE rp.role_id = r.id AND rp.permission_id = p.id)"
            ),
            {"role": role, "codes": codes},
        )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.scalar(sa.text("SELECT count(*) FROM fog_collector_relocations")):
        raise RuntimeError("Existen solicitudes de reubicación; revertir esta migración las eliminaría.")

    conn.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = ANY(:codes))"
        ),
        {"codes": list(NEW_PERMISSIONS)},
    )
    conn.execute(sa.text("DELETE FROM permissions WHERE code = ANY(:codes)"), {"codes": list(NEW_PERMISSIONS)})
    # El permiso de consulta de infraestructura otorgado a mantenimiento se conserva: es inocuo y
    # puede haber existido antes de esta migración.

    op.drop_constraint(
        op.f("fk_notifications_relocation_id_fog_collector_relocations"), "notifications", type_="foreignkey"
    )
    op.drop_column("notifications", "relocation_id")
    op.drop_index("uq_fog_collector_relocations_activa", table_name="fog_collector_relocations")
    for column in ("assigned_to_id", "requested_by_id", "fog_collector_id"):
        op.drop_index(op.f(f"ix_fog_collector_relocations_{column}"), table_name="fog_collector_relocations")
    op.drop_table("fog_collector_relocations")
