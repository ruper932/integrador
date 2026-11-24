"""Importa todos los modelos para que Alembic y SQLAlchemy los registren."""

from app.data.models.incidents import IncidentReport, Notification
from app.data.models.infrastructure import FogCollector, Greenhouse, Location, Tank
from app.data.models.inventory import (
    InventoryCategory,
    InventoryCount,
    InventoryItem,
    InventoryItemCompatibility,
    InventoryMovement,
    InventoryMovementType,
    InventoryPeriod,
    InventoryPeriodBalance,
    MaintenanceItem,
    MaintenanceRecord,
)
from app.data.models.iot import (
    Device,
    DeviceCredential,
    DeviceLocation,
    FirmwareRelease,
    MeasurementBatch,
    Sensor,
    SensorCalibration,
    SensorReading,
    SensorType,
)
from app.data.models.people import AcademicLevel, Institution, Position, UserDegree, UserProfile
from app.data.models.relocations import FogCollectorRelocation
from app.data.models.security import AccountRecoveryRequest, AuditLog, Permission, Role, User, UserSession

__all__ = [
    "AcademicLevel",
    "Institution",
    "Position",
    "UserDegree",
    "UserProfile",
    "AccountRecoveryRequest",
    "AuditLog",
    "Device",
    "DeviceCredential",
    "DeviceLocation",
    "FirmwareRelease",
    "FogCollector",
    "FogCollectorRelocation",
    "Greenhouse",
    "IncidentReport",
    "InventoryCategory",
    "InventoryCount",
    "InventoryPeriod",
    "InventoryPeriodBalance",
    "InventoryItem",
    "InventoryItemCompatibility",
    "InventoryMovement",
    "InventoryMovementType",
    "Location",
    "MaintenanceItem",
    "MaintenanceRecord",
    "MeasurementBatch",
    "Notification",
    "Permission",
    "Role",
    "Sensor",
    "SensorCalibration",
    "SensorReading",
    "SensorType",
    "Tank",
    "User",
    "UserSession",
]
