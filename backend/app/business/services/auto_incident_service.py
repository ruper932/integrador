"""Incidencias automáticas: el sistema abre reportes de incidencia por sí mismo.

Causas detectadas:
- `sin_comunicacion`: una estación activa no envía datos desde hace `auto_incident_offline_hours`.
- `lecturas_anomalas`: un sensor activo acumula `auto_incident_anomaly_threshold` lecturas rechazadas
  (fuera de rango, unidad inválida o inválidas) en las últimas `auto_incident_anomaly_window_hours`.

El reporte sigue el flujo normal (mantenimiento acepta, inicia y finaliza). No se duplica mientras
exista uno de la misma causa sin finalizar, ni durante la ventana de la causa tras finalizarlo.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.business.services.audit_service import AuditService
from app.business.services.context import RequestContext
from app.business.services.notification_service import NotificationService
from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.permissions import Permission
from app.data.models.incidents import IncidentReport
from app.data.models.iot import Device
from app.data.repositories.incidents import IncidentReportRepository
from app.data.repositories.iot import DeviceRepository, SensorReadingRepository
from app.data.repositories.security import UserRepository

SYSTEM = RequestContext(user=None)


class AutoIncidentService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.settings = get_settings()
        self.reports = IncidentReportRepository(session)
        self.devices = DeviceRepository(session)
        self.readings = SensorReadingRepository(session)
        self.users = UserRepository(session)
        self.notifications = NotificationService(session)
        self.audit = AuditService(session)

    def run(self) -> list[IncidentReport]:
        """Revisa estaciones y sensores; devuelve los reportes abiertos en esta pasada."""
        # Si varios procesos de la API revisan a la vez, solo uno abre reportes.
        self.reports.lock_auto_detection()
        now = utcnow()
        created = self._offline(now) + self._anomalies(now)
        self.session.commit()
        return created

    def _offline(self, now: datetime) -> list[IncidentReport]:
        window = timedelta(hours=self.settings.auto_incident_offline_hours)
        created = []
        for device in self.devices.list_silent_since(now - window):
            if self.reports.has_pending_auto(
                device_id=device.id, cause="sin_comunicacion", sensor_id=None, finished_since=now - window
            ):
                continue
            last = f"desde el {self._local(device.last_seen_at)}" if device.last_seen_at else "desde su registro"
            created.append(
                self._open(
                    device,
                    cause="sin_comunicacion",
                    sensor_id=None,
                    priority="alta",
                    title=f"Estación {device.code} sin comunicación",
                    description=(
                        f"La estación «{device.name}» ({device.code}) no envía datos {last}. "
                        "Revise la alimentación, la conexión Wi-Fi y el estado del ESP32."
                    ),
                )
            )
        return created

    def _anomalies(self, now: datetime) -> list[IncidentReport]:
        hours = self.settings.auto_incident_anomaly_window_hours
        since = now - timedelta(hours=hours)
        created = []
        for sensor, count in self.readings.anomalous_sensors(
            since=since, threshold=self.settings.auto_incident_anomaly_threshold
        ):
            if self.reports.has_pending_auto(
                device_id=sensor.device_id, cause="lecturas_anomalas", sensor_id=sensor.id, finished_since=since
            ):
                continue
            device = sensor.device
            created.append(
                self._open(
                    device,
                    cause="lecturas_anomalas",
                    sensor_id=sensor.id,
                    priority="media",
                    title=f"Lecturas anómalas en el sensor {sensor.code} ({device.code})",
                    description=(
                        f"El sensor {sensor.code} de la estación «{device.name}» registró {count} lecturas "
                        f"rechazadas (fuera de rango o inválidas) en las últimas {hours} h. "
                        "Revise la conexión, la calibración o el estado del sensor."
                    ),
                )
            )
        return created

    def _open(
        self, device: Device, *, cause: str, sensor_id: int | None, priority: str, title: str, description: str
    ) -> IncidentReport:
        report = self.reports.add(
            IncidentReport(
                source="sistema",
                auto_cause=cause,
                reported_by_id=None,
                title=title,
                description=description,
                priority=priority,
                location_reference=device.fog_collector.name if device.fog_collector else None,
                device_id=device.id,
                sensor_id=sensor_id,
            )
        )
        recipients = [
            u.id
            for code in (Permission.INCIDENTS_ATTEND, Permission.INCIDENTS_SUPERVISE)
            for u in self.users.active_with_permission(code)
        ]
        self.notifications.notify(
            recipients,
            "Incidencia detectada por el sistema",
            f"{title} (prioridad {priority}).",
            incident_report_id=report.id,
        )
        self.audit.record(
            SYSTEM,
            "incidencia.reportar_automatica",
            entity_type="incident_report",
            entity_id=report.id,
            details={"causa": cause, "device_id": device.id, "sensor_id": sensor_id},
        )
        return report

    def _local(self, moment: datetime) -> str:
        return moment.astimezone(ZoneInfo(self.settings.local_timezone)).strftime("%d/%m/%Y %H:%M")
