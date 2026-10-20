"""datos de referencia

Carga roles, permisos, tipos de sensor, categorías de inventario y tipos de
movimiento. Los datos se copian aquí (y no se importan desde la aplicación)
para que la migración sea reproducible aunque el código evolucione.

Revision ID: 20fc4a8e176b
Revises: ac467e2ffc3d
Create Date: 2026-10-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20fc4a8e176b"
down_revision: str | Sequence[str] | None = "ac467e2ffc3d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = {
    "usuarios.gestionar": "Crear, editar y desactivar usuarios",
    "roles.gestionar": "Administrar roles y permisos",
    "auditoria.consultar": "Consultar la auditoría",
    "recuperacion.gestionar": "Aprobar o rechazar solicitudes de recuperación de cuenta",
    "infraestructura.consultar": "Consultar dispositivos, sensores y atrapanieblas",
    "infraestructura.gestionar": "Gestionar dispositivos, sensores y atrapanieblas",
    "dashboard.consultar": "Consultar el dashboard",
    "mediciones.consultar": "Consultar históricos de mediciones",
    "predicciones.consultar": "Consultar predicciones y comparativas",
    "predicciones.generar": "Generar predicciones",
    "reportes.consultar": "Consultar reportes autorizados",
    "reportes.generar": "Generar y exportar reportes",
    "inventario.consultar": "Consultar inventario de repuestos",
    "inventario.gestionar": "Gestionar inventario de repuestos",
    "mantenimiento.consultar": "Consultar mantenimientos",
    "mantenimiento.registrar": "Registrar mantenimientos",
    "respaldos.gestionar": "Gestionar respaldos",
    "configuracion.gestionar": "Acceder a la configuración técnica",
}

ROLES = {
    "administrador": ("Administración completa del sistema", list(PERMISSIONS)),
    "director_docente": (
        "Director o docente: consulta y generación de reportes",
        [
            "dashboard.consultar",
            "mediciones.consultar",
            "infraestructura.consultar",
            "predicciones.consultar",
            "predicciones.generar",
            "reportes.consultar",
            "reportes.generar",
            "inventario.consultar",
            "mantenimiento.consultar",
        ],
    ),
    "observador": (
        "Observador: consulta de dashboard, históricos y reportes autorizados",
        ["dashboard.consultar", "mediciones.consultar", "reportes.consultar"],
    ),
    "mantenimiento": (
        "Rol complementario que habilita el registro de mantenimientos",
        ["mantenimiento.consultar", "mantenimiento.registrar", "inventario.consultar", "infraestructura.consultar"],
    ),
}

# (código, nombre, unidad, mínimo, máximo, agregación, descripción)
SENSOR_TYPES = [
    ("temperatura", "Temperatura del aire", "C", -30, 60, "instantaneo", None),
    ("humedad_relativa", "Humedad relativa", "%", 0, 100, "instantaneo", None),
    ("presion_atmosferica", "Presión atmosférica", "hPa", 300, 1100, "instantaneo", None),
    ("velocidad_viento", "Velocidad del viento", "m/s", 0, 75, "instantaneo", None),
    ("direccion_viento", "Dirección del viento", "deg", 0, 360, "instantaneo", "0 = norte, sentido horario"),
    ("niebla", "Intensidad de niebla", "%", 0, 100, "instantaneo", "0 = sin niebla, 100 = niebla densa"),
    (
        "volumen_captado",
        "Volumen de agua captada",
        "L",
        0,
        1000,
        "incremental",
        "Litros captados desde la lectura anterior (valor incremental, no acumulado).",
    ),
    (
        "nivel_almacenamiento",
        "Nivel de almacenamiento del tanque",
        "cm",
        0,
        1000,
        "instantaneo",
        "Altura de agua en el tanque al momento de la medición.",
    ),
]

INVENTORY_CATEGORIES = [
    "Microcontroladores",
    "Sensores ambientales",
    "Sensores hídricos",
    "Energía y alimentación",
    "Protección ambiental",
    "Conectividad y cableado",
    "Estructura y fijaciones",
    "Herramientas",
    "Consumibles",
]

MOVEMENT_TYPES = [
    ("entrada", "Entrada", 1, True),
    ("salida", "Salida", -1, True),
    ("salida_mantenimiento", "Salida por mantenimiento", -1, False),
]


def upgrade() -> None:
    conn = op.get_bind()

    permissions = sa.table("permissions", sa.column("id", sa.Integer), sa.column("code"), sa.column("description"))
    roles = sa.table(
        "roles", sa.column("id", sa.Integer), sa.column("name"), sa.column("description"), sa.column("is_system")
    )
    role_permissions = sa.table("role_permissions", sa.column("role_id"), sa.column("permission_id"))

    op.bulk_insert(permissions, [{"code": c, "description": d} for c, d in PERMISSIONS.items()])
    op.bulk_insert(roles, [{"name": n, "description": d, "is_system": True} for n, (d, _) in ROLES.items()])

    perm_ids = dict(conn.execute(sa.text("SELECT code, id FROM permissions")).fetchall())
    role_ids = dict(conn.execute(sa.text("SELECT name, id FROM roles")).fetchall())
    op.bulk_insert(
        role_permissions,
        [
            {"role_id": role_ids[name], "permission_id": perm_ids[code]}
            for name, (_, codes) in ROLES.items()
            for code in codes
        ],
    )

    sensor_types = sa.table(
        "sensor_types",
        sa.column("code"),
        sa.column("name"),
        sa.column("unit"),
        sa.column("min_value"),
        sa.column("max_value"),
        sa.column("aggregation"),
        sa.column("description"),
    )
    op.bulk_insert(
        sensor_types,
        [
            dict(
                zip(["code", "name", "unit", "min_value", "max_value", "aggregation", "description"], row, strict=True)
            )
            for row in SENSOR_TYPES
        ],
    )

    categories = sa.table("inventory_categories", sa.column("name"), sa.column("is_active"))
    op.bulk_insert(categories, [{"name": n, "is_active": True} for n in INVENTORY_CATEGORIES])

    movement_types = sa.table(
        "inventory_movement_types",
        sa.column("code"),
        sa.column("name"),
        sa.column("direction"),
        sa.column("manual_allowed"),
    )
    op.bulk_insert(
        movement_types,
        [{"code": c, "name": n, "direction": d, "manual_allowed": m} for c, n, d, m in MOVEMENT_TYPES],
    )


def downgrade() -> None:
    op.execute("DELETE FROM inventory_movement_types")
    op.execute("DELETE FROM inventory_categories")
    op.execute("DELETE FROM sensor_types")
    op.execute("DELETE FROM role_permissions")
    op.execute("DELETE FROM roles WHERE is_system")
    op.execute("DELETE FROM permissions")
