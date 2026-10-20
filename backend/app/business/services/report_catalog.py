"""Catálogo de reportes: módulo, permiso requerido y filtros que admite cada uno.

Es la única fuente de verdad: el backend lo usa para autorizar y describir los filtros aplicados,
y el frontend arma el formulario de cada reporte a partir de él.
"""

from dataclasses import dataclass

from app.core.permissions import Permission

# Filtros disponibles (nombre del parámetro → etiqueta para el usuario y para el encabezado del reporte).
FILTER_LABELS: dict[str, str] = {
    "date_range": "Periodo",
    "bucket": "Agrupación",
    "device_id": "Dispositivo",
    "sensor_type": "Variable",
    "fog_collector_id": "Atrapanieblas",
    "quality": "Calidad de la lectura",
    "device_status": "Estado del dispositivo",
    "category_id": "Categoría",
    "item_id": "Repuesto",
    "condition": "Estado del repuesto",
    "low_stock_only": "Solo stock bajo",
    "include_inactive": "Incluir desactivados",
    "movement_type": "Tipo de movimiento",
    "period_id": "Periodo de inventario",
    "maintenance_type": "Tipo de mantenimiento",
    "final_status": "Estado final del componente",
    "responsible_id": "Responsable",
    "origin": "Origen",
    "incident_status": "Estado del reporte",
    "priority": "Prioridad",
    "reporter_id": "Reportado por",
    "role_id": "Rol",
    "position_id": "Cargo",
    "is_active": "Estado de la cuenta",
    "action": "Acción",
    "actor_id": "Usuario",
}

# Código de error cuando falta un filtro obligatorio (se conservan los códigos ya publicados).
REQUIRED_ERROR_CODES = {
    "sensor_type": "variable_requerida",
    "period_id": "periodo_requerido",
    "item_id": "repuesto_requerido",
}


@dataclass(frozen=True)
class ReportDefinition:
    kind: str
    module: str
    label: str
    description: str
    permissions: tuple[Permission, ...]  # además de `reportes.generar`
    filters: tuple[str, ...]
    required: tuple[str, ...] = ()


MODULE_IOT = "Monitoreo IoT y volumen"
MODULE_INVENTORY = "Inventario"
MODULE_MAINTENANCE = "Mantenimiento"
MODULE_INCIDENTS = "Reportes de incidencia"
MODULE_ADMIN = "Usuarios y auditoría"

REPORTS: tuple[ReportDefinition, ...] = (
    ReportDefinition(
        "volumen",
        MODULE_IOT,
        "Volumen de agua captada",
        "Litros captados por hora, día, semana o mes (suma de lecturas válidas).",
        (Permission.MEASUREMENTS_READ,),
        ("date_range", "bucket", "device_id", "fog_collector_id"),
    ),
    ReportDefinition(
        "variable",
        MODULE_IOT,
        "Variable ambiental agregada",
        "Promedio, mínimo y máximo de una variable por intervalo.",
        (Permission.MEASUREMENTS_READ,),
        ("date_range", "bucket", "sensor_type", "device_id", "fog_collector_id"),
        required=("sensor_type",),
    ),
    ReportDefinition(
        "mediciones",
        MODULE_IOT,
        "Histórico de mediciones (detalle)",
        "Cada lectura recibida, con su fecha de medición, recepción y calidad.",
        (Permission.MEASUREMENTS_READ,),
        ("date_range", "sensor_type", "device_id", "fog_collector_id", "quality"),
    ),
    ReportDefinition(
        "dispositivos",
        MODULE_IOT,
        "Estado de las estaciones",
        "Dispositivos, sensores y última comunicación (al día o desactualizados).",
        (Permission.INFRASTRUCTURE_READ,),
        ("device_status", "fog_collector_id"),
    ),
    ReportDefinition(
        "inventario_stock",
        MODULE_INVENTORY,
        "Stock actual",
        "Existencias, stock mínimo y necesidad de reposición.",
        (Permission.INVENTORY_READ,),
        ("category_id", "condition", "low_stock_only", "include_inactive"),
    ),
    ReportDefinition(
        "inventario_movimientos",
        MODULE_INVENTORY,
        "Movimientos",
        "Entradas, salidas y ajustes por fecha efectiva.",
        (Permission.INVENTORY_READ,),
        ("date_range", "category_id", "item_id", "movement_type"),
    ),
    ReportDefinition(
        "inventario_periodo",
        MODULE_INVENTORY,
        "Resumen del periodo (valorizado)",
        "Saldos inicial y final, entradas, salidas, ajustes y valor por costo promedio.",
        (Permission.INVENTORY_READ,),
        ("period_id", "category_id"),
        required=("period_id",),
    ),
    ReportDefinition(
        "inventario_conteo",
        MODULE_INVENTORY,
        "Planilla / acta de conteo físico",
        "Saldo según registros frente a lo contado, con líneas de firma.",
        (Permission.INVENTORY_READ,),
        ("period_id", "category_id"),
        required=("period_id",),
    ),
    ReportDefinition(
        "inventario_kardex",
        MODULE_INVENTORY,
        "Kardex por repuesto",
        "Movimientos de un repuesto con su saldo acumulado.",
        (Permission.INVENTORY_READ,),
        ("item_id", "date_range"),
        required=("item_id",),
    ),
    ReportDefinition(
        "inventario_consumo",
        MODULE_INVENTORY,
        "Consumo por mantenimiento",
        "Repuestos utilizados en mantenimientos, por dispositivo.",
        (Permission.INVENTORY_READ, Permission.MAINTENANCE_READ),
        ("date_range", "device_id", "category_id", "item_id"),
    ),
    ReportDefinition(
        "mantenimientos",
        MODULE_MAINTENANCE,
        "Mantenimientos realizados",
        "Mantenimientos finalizados con su responsable, repuestos y estado final.",
        (Permission.MAINTENANCE_READ,),
        ("date_range", "device_id", "maintenance_type", "final_status", "responsible_id", "origin"),
    ),
    ReportDefinition(
        "incidencias",
        MODULE_INCIDENTS,
        "Reportes de incidencia y su atención",
        "Quién reportó, quién atendió, estado y tiempos de atención.",
        (Permission.INCIDENTS_SUPERVISE,),
        ("date_range", "incident_status", "priority", "device_id", "reporter_id", "responsible_id"),
    ),
    ReportDefinition(
        "usuarios",
        MODULE_ADMIN,
        "Usuarios registrados",
        "Datos de contacto, cargo, roles y estado de cada cuenta.",
        (Permission.USERS_MANAGE,),
        ("role_id", "position_id", "is_active"),
    ),
    ReportDefinition(
        "auditoria",
        MODULE_ADMIN,
        "Auditoría",
        "Operaciones registradas: quién, qué, cuándo y desde qué equipo.",
        (Permission.AUDIT_READ,),
        ("date_range", "action", "actor_id"),
    ),
)

BY_KIND: dict[str, ReportDefinition] = {r.kind: r for r in REPORTS}


def available_for(permission_codes: set[str]) -> list[ReportDefinition]:
    if Permission.REPORTS_GENERATE.value not in permission_codes:
        return []
    return [r for r in REPORTS if all(p.value in permission_codes for p in r.permissions)]
