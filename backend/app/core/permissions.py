"""Catálogo de permisos del sistema (RBAC).

Los roles y su asignación inicial de permisos se cargan mediante la migración
Alembic inicial; el administrador puede modificar la asignación desde la API.
"""

from enum import StrEnum


class Permission(StrEnum):
    USERS_MANAGE = "usuarios.gestionar"
    ROLES_MANAGE = "roles.gestionar"
    AUDIT_READ = "auditoria.consultar"
    RECOVERY_MANAGE = "recuperacion.gestionar"
    INFRASTRUCTURE_READ = "infraestructura.consultar"
    INFRASTRUCTURE_MANAGE = "infraestructura.gestionar"
    DASHBOARD_READ = "dashboard.consultar"
    MEASUREMENTS_READ = "mediciones.consultar"
    PREDICTIONS_READ = "predicciones.consultar"
    PREDICTIONS_GENERATE = "predicciones.generar"
    REPORTS_READ = "reportes.consultar"
    REPORTS_GENERATE = "reportes.generar"
    INVENTORY_READ = "inventario.consultar"
    INVENTORY_MANAGE = "inventario.gestionar"
    MAINTENANCE_READ = "mantenimiento.consultar"
    MAINTENANCE_REGISTER = "mantenimiento.registrar"
    INCIDENTS_REPORT = "incidencias.reportar"
    INCIDENTS_ATTEND = "incidencias.atender"
    INCIDENTS_SUPERVISE = "incidencias.supervisar"
    BACKUPS_MANAGE = "respaldos.gestionar"
    SETTINGS_MANAGE = "configuracion.gestionar"


PERMISSION_DESCRIPTIONS: dict[Permission, str] = {
    Permission.USERS_MANAGE: "Crear, editar y desactivar usuarios",
    Permission.ROLES_MANAGE: "Administrar roles y permisos",
    Permission.AUDIT_READ: "Consultar la auditoría",
    Permission.RECOVERY_MANAGE: "Aprobar o rechazar solicitudes de recuperación de cuenta",
    Permission.INFRASTRUCTURE_READ: "Consultar dispositivos, sensores y atrapanieblas",
    Permission.INFRASTRUCTURE_MANAGE: "Gestionar dispositivos, sensores y atrapanieblas",
    Permission.DASHBOARD_READ: "Consultar el dashboard",
    Permission.MEASUREMENTS_READ: "Consultar históricos de mediciones",
    Permission.PREDICTIONS_READ: "Consultar predicciones y comparativas",
    Permission.PREDICTIONS_GENERATE: "Generar predicciones",
    Permission.REPORTS_READ: "Consultar reportes autorizados",
    Permission.REPORTS_GENERATE: "Generar y exportar reportes",
    Permission.INVENTORY_READ: "Consultar inventario de repuestos",
    Permission.INVENTORY_MANAGE: "Gestionar inventario de repuestos",
    Permission.MAINTENANCE_READ: "Consultar mantenimientos",
    Permission.MAINTENANCE_REGISTER: "Registrar mantenimientos",
    Permission.INCIDENTS_REPORT: "Reportar incidencias y seguir el estado de los propios reportes",
    Permission.INCIDENTS_ATTEND: "Recibir, aceptar y atender reportes de incidencia",
    Permission.INCIDENTS_SUPERVISE: "Consultar todos los reportes de incidencia y su seguimiento",
    Permission.BACKUPS_MANAGE: "Gestionar respaldos",
    Permission.SETTINGS_MANAGE: "Acceder a la configuración técnica",
}

ROLE_ADMIN = "administrador"
ROLE_DIRECTOR = "director"
ROLE_TEACHER = "docente"
ROLE_MAINTENANCE = "mantenimiento"
