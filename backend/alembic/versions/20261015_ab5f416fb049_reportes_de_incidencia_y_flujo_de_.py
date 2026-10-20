"""reportes de incidencia y flujo de mantenimiento

- `incident_reports`: situaciones reportadas por docentes; `notifications`: avisos internos.
- `maintenance_records` incorpora el estado (aceptado → en_progreso → finalizado), el reporte que
  atiende y las fechas de cada etapa. Los detalles del trabajo pueden quedar vacíos mientras el
  mantenimiento no esté finalizado (restricción CHECK). Los registros existentes quedan `finalizado`.
- Roles: `director_docente` pasa a `director` y `observador` pasa a `docente` (se renombran: los
  usuarios conservan su asignación). Se agregan los permisos de incidencias.

El downgrade no elimina información: se niega a continuar si ya existen reportes de incidencia o
mantenimientos sin finalizar.

Revision ID: ab5f416fb049
Revises: 4a0be0c67e25
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "ab5f416fb049"
down_revision: str | Sequence[str] | None = "4a0be0c67e25"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_PERMISSIONS = {
    "incidencias.reportar": "Reportar incidencias y seguir el estado de los propios reportes",
    "incidencias.atender": "Recibir, aceptar y atender reportes de incidencia",
    "incidencias.supervisar": "Consultar todos los reportes de incidencia y su seguimiento",
}

# (nombre anterior, nombre nuevo, descripción nueva, descripción anterior)
ROLE_RENAMES = [
    (
        "director_docente",
        "director",
        "Director/a: supervisión, reportes y seguimiento de mantenimientos",
        "Director o docente: consulta y generación de reportes",
    ),
    (
        "observador",
        "docente",
        "Docente: consulta del dashboard e históricos y reporte de incidencias",
        "Observador: consulta de dashboard, históricos y reportes autorizados",
    ),
]
MAINTENANCE_ROLE_DESCRIPTIONS = (
    "Personal de mantenimiento: atención de reportes de incidencia y registro de mantenimientos",
    "Rol complementario que habilita el registro de mantenimientos",
)

GRANTS = {
    "administrador": list(NEW_PERMISSIONS),
    "director": ["incidencias.reportar", "incidencias.supervisar"],
    # El docente consulta dispositivos y sensores para indicar qué componente presenta la falla.
    "docente": ["incidencias.reportar", "infraestructura.consultar"],
    "mantenimiento": ["incidencias.atender", "dashboard.consultar"],
}

MAINTENANCE_STATUSES = "('aceptado', 'en_progreso', 'finalizado')"


def upgrade() -> None:
    op.create_table(
        "incident_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reported_by_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=10), nullable=False),
        sa.Column("location_reference", sa.String(length=200), nullable=True),
        sa.Column("device_id", sa.Integer(), nullable=True),
        sa.Column("sensor_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("priority IN ('baja', 'media', 'alta')", name=op.f("ck_incident_reports_priority")),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], name=op.f("fk_incident_reports_device_id_devices")),
        sa.ForeignKeyConstraint(
            ["reported_by_id"], ["users.id"], name=op.f("fk_incident_reports_reported_by_id_users")
        ),
        sa.ForeignKeyConstraint(["sensor_id"], ["sensors.id"], name=op.f("fk_incident_reports_sensor_id_sensors")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_reports")),
    )
    op.create_index(op.f("ix_incident_reports_device_id"), "incident_reports", ["device_id"], unique=False)
    op.create_index(op.f("ix_incident_reports_reported_by_id"), "incident_reports", ["reported_by_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("incident_report_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["incident_report_id"],
            ["incident_reports.id"],
            name=op.f("fk_notifications_incident_report_id_incident_reports"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_notifications_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index(op.f("ix_notifications_created_at"), "notifications", ["created_at"], unique=False)
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)

    op.add_column(
        "maintenance_records",
        sa.Column("status", sa.String(length=15), server_default="finalizado", nullable=False),
    )
    op.add_column("maintenance_records", sa.Column("incident_report_id", sa.Integer(), nullable=True))
    op.add_column("maintenance_records", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("maintenance_records", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("maintenance_records", sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True))
    # Los mantenimientos ya registrados se consideran finalizados en la fecha en que se realizaron.
    op.execute("UPDATE maintenance_records SET finished_at = performed_at")
    for column, type_ in [
        ("device_id", sa.INTEGER()),
        ("performed_at", postgresql.TIMESTAMP(timezone=True)),
        ("maintenance_type", sa.VARCHAR(length=20)),
        ("description", sa.TEXT()),
        ("final_status", sa.VARCHAR(length=30)),
    ]:
        op.alter_column("maintenance_records", column, existing_type=type_, nullable=True)
    op.create_check_constraint("status", "maintenance_records", f"status IN {MAINTENANCE_STATUSES}")
    op.create_check_constraint(
        "finalizado_completo",
        "maintenance_records",
        "status <> 'finalizado' OR (device_id IS NOT NULL AND performed_at IS NOT NULL"
        " AND maintenance_type IS NOT NULL AND description IS NOT NULL AND final_status IS NOT NULL)",
    )
    op.create_unique_constraint(
        op.f("uq_maintenance_records_incident_report_id"), "maintenance_records", ["incident_report_id"]
    )
    op.create_foreign_key(
        op.f("fk_maintenance_records_incident_report_id_incident_reports"),
        "maintenance_records",
        "incident_reports",
        ["incident_report_id"],
        ["id"],
    )

    # --- Roles y permisos ---------------------------------------------------------
    conn = op.get_bind()
    for old, new, description, _ in ROLE_RENAMES:
        conn.execute(
            sa.text("UPDATE roles SET name = :new, description = :description WHERE name = :old"),
            {"old": old, "new": new, "description": description},
        )
    conn.execute(
        sa.text("UPDATE roles SET description = :d WHERE name = 'mantenimiento'"),
        {"d": MAINTENANCE_ROLE_DESCRIPTIONS[0]},
    )
    permissions = sa.table("permissions", sa.column("code"), sa.column("description"))
    op.bulk_insert(permissions, [{"code": c, "description": d} for c, d in NEW_PERMISSIONS.items()])
    for role, codes in GRANTS.items():
        # Si el administrador ya otorgó alguno de estos permisos, no se duplica.
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
    pending = conn.scalar(
        sa.text(
            "SELECT (SELECT count(*) FROM incident_reports)"
            " + (SELECT count(*) FROM maintenance_records WHERE status <> 'finalizado')"
        )
    )
    if pending:
        raise RuntimeError(
            "Existen reportes de incidencia o mantenimientos sin finalizar; revertir esta migración los eliminaría."
        )

    conn.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = ANY(:codes))"
        ),
        {"codes": list(NEW_PERMISSIONS)},
    )
    conn.execute(sa.text("DELETE FROM permissions WHERE code = ANY(:codes)"), {"codes": list(NEW_PERMISSIONS)})
    # Los permisos de consulta añadidos a docente y mantenimiento se retiran.
    conn.execute(
        sa.text(
            "DELETE FROM role_permissions WHERE "
            "(role_id, permission_id) IN (SELECT r.id, p.id FROM roles r, permissions p WHERE "
            "(r.name = 'docente' AND p.code = 'infraestructura.consultar') OR "
            "(r.name = 'mantenimiento' AND p.code = 'dashboard.consultar'))"
        )
    )
    for old, new, _, old_description in ROLE_RENAMES:
        conn.execute(
            sa.text("UPDATE roles SET name = :old, description = :description WHERE name = :new"),
            {"old": old, "new": new, "description": old_description},
        )
    conn.execute(
        sa.text("UPDATE roles SET description = :d WHERE name = 'mantenimiento'"),
        {"d": MAINTENANCE_ROLE_DESCRIPTIONS[1]},
    )

    op.drop_constraint(
        op.f("fk_maintenance_records_incident_report_id_incident_reports"), "maintenance_records", type_="foreignkey"
    )
    op.drop_constraint(op.f("uq_maintenance_records_incident_report_id"), "maintenance_records", type_="unique")
    op.drop_constraint(op.f("ck_maintenance_records_finalizado_completo"), "maintenance_records", type_="check")
    op.drop_constraint(op.f("ck_maintenance_records_status"), "maintenance_records", type_="check")
    for column, type_ in [
        ("final_status", sa.VARCHAR(length=30)),
        ("description", sa.TEXT()),
        ("maintenance_type", sa.VARCHAR(length=20)),
        ("performed_at", postgresql.TIMESTAMP(timezone=True)),
        ("device_id", sa.INTEGER()),
    ]:
        op.alter_column("maintenance_records", column, existing_type=type_, nullable=False)
    for column in ("finished_at", "started_at", "accepted_at", "incident_report_id", "status"):
        op.drop_column("maintenance_records", column)
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_created_at"), table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(op.f("ix_incident_reports_reported_by_id"), table_name="incident_reports")
    op.drop_index(op.f("ix_incident_reports_device_id"), table_name="incident_reports")
    op.drop_table("incident_reports")
