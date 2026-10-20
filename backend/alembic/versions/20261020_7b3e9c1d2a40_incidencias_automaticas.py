"""incidencias automaticas

Permite que el sistema abra reportes de incidencia por sí mismo (estación sin comunicación o
sensor con lecturas anómalas). Agrega `incident_reports.source` y `incident_reports.auto_cause`, y
`reported_by_id` pasa a ser opcional solo para los reportes del sistema. Los reportes existentes
quedan como `source = 'usuario'`; no se modifica ni elimina ningún dato.

Revision ID: 7b3e9c1d2a40
Revises: dd5c474a8961
Create Date: 2026-10-20
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "7b3e9c1d2a40"
down_revision: str | Sequence[str] | None = "dd5c474a8961"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "incident_reports",
        sa.Column("source", sa.String(length=10), nullable=False, server_default="usuario"),
    )
    op.add_column("incident_reports", sa.Column("auto_cause", sa.String(length=30), nullable=True))
    op.alter_column("incident_reports", "reported_by_id", existing_type=sa.Integer(), nullable=True)
    op.create_check_constraint("source", "incident_reports", "source IN ('usuario', 'sistema')")
    op.create_check_constraint(
        "auto_cause",
        "incident_reports",
        "auto_cause IS NULL OR auto_cause IN ('sin_comunicacion', 'lecturas_anomalas')",
    )
    # Un reporte de usuario siempre tiene autor; uno del sistema nunca, y siempre indica la causa.
    op.create_check_constraint(
        "source_consistency",
        "incident_reports",
        "(source = 'usuario' AND reported_by_id IS NOT NULL AND auto_cause IS NULL)"
        " OR (source = 'sistema' AND reported_by_id IS NULL AND auto_cause IS NOT NULL)",
    )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.execute(sa.text("SELECT 1 FROM incident_reports WHERE source = 'sistema' LIMIT 1")).first():
        # Volver atrás perdería los reportes automáticos: se exige revisarlos antes.
        raise RuntimeError("Existen reportes automáticos; no se puede revertir sin perder datos.")
    op.drop_constraint(op.f("ck_incident_reports_source_consistency"), "incident_reports", type_="check")
    op.drop_constraint(op.f("ck_incident_reports_auto_cause"), "incident_reports", type_="check")
    op.drop_constraint(op.f("ck_incident_reports_source"), "incident_reports", type_="check")
    op.alter_column("incident_reports", "reported_by_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("incident_reports", "auto_cause")
    op.drop_column("incident_reports", "source")
