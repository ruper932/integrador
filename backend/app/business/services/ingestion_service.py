"""Recepción de lotes de mediciones enviados por los ESP32.

Garantías:
- Idempotencia por lote (batch_id por dispositivo) y por lectura (message_id global).
- Validación de sensor asociado y activo, fecha, unidad y rango antes de almacenar.
- Las lecturas con problemas de calidad se guardan marcadas (nunca como válidas)
  para trazabilidad; las lecturas sin contexto válido se rechazan sin guardarse.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.business.rules.measurements import ReadingRejected, assess_value, check_timestamp
from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.errors import BusinessRuleError
from app.data.models.iot import Device, MeasurementBatch, SensorReading
from app.data.repositories.iot import MeasurementBatchRepository, SensorReadingRepository, SensorRepository


@dataclass(frozen=True)
class IncomingReading:
    message_id: uuid.UUID
    sensor_code: str
    measured_at: datetime
    value: float | None
    unit: str


@dataclass
class ReadingOutcome:
    message_id: uuid.UUID
    status: str  # aceptada | almacenada_con_observacion | rechazada | duplicada
    quality: str | None = None
    detail: str | None = None


@dataclass
class BatchOutcome:
    batch_uid: uuid.UUID
    status: str  # procesado | duplicado
    received_at: datetime
    accepted: int = 0
    invalid: int = 0
    rejected: int = 0
    duplicates: int = 0
    results: list[ReadingOutcome] = field(default_factory=list)


class IngestionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.batches = MeasurementBatchRepository(session)
        self.readings = SensorReadingRepository(session)
        self.sensors = SensorRepository(session)
        self.settings = get_settings()

    def ingest(
        self,
        device: Device,
        *,
        batch_uid: uuid.UUID,
        sent_at: datetime | None,
        firmware_version: str | None,
        readings: list[IncomingReading],
    ) -> BatchOutcome:
        if len(readings) > self.settings.max_readings_per_batch:
            raise BusinessRuleError(
                f"El lote supera el máximo de {self.settings.max_readings_per_batch} lecturas.", code="lote_muy_grande"
            )
        now = utcnow()
        previous = self.batches.get_by_uid(device.id, batch_uid)
        if previous is not None:
            # Reenvío de un lote ya procesado: el dispositivo sí se comunicó.
            device.last_seen_at = now
            self.session.commit()
            return self._duplicate_batch(previous)

        max_skew = timedelta(seconds=self.settings.measurement_max_future_skew_seconds)
        sensors_by_code = {s.code: s for s in self.sensors.list_by_device(device.id)}
        already_stored = self.readings.existing_message_uids([r.message_id for r in readings])
        seen: set[uuid.UUID] = set()

        batch = self.batches.add(
            MeasurementBatch(device_id=device.id, batch_uid=batch_uid, sent_at=sent_at, readings_count=len(readings))
        )
        outcome = BatchOutcome(batch_uid=batch_uid, status="procesado", received_at=now)

        for reading in readings:
            if reading.message_id in already_stored or reading.message_id in seen:
                outcome.duplicates += 1
                outcome.results.append(ReadingOutcome(reading.message_id, "duplicada"))
                continue
            seen.add(reading.message_id)
            try:
                sensor = sensors_by_code.get(reading.sensor_code)
                if sensor is None:
                    raise ReadingRejected(f"El sensor '{reading.sensor_code}' no está asociado al dispositivo.")
                if sensor.status != "activo":
                    raise ReadingRejected(f"El sensor '{reading.sensor_code}' no está activo.")
                check_timestamp(reading.measured_at, now=now, max_future_skew=max_skew)
            except ReadingRejected as exc:
                outcome.rejected += 1
                outcome.results.append(ReadingOutcome(reading.message_id, "rechazada", detail=exc.reason))
                continue

            assessment = assess_value(sensor.sensor_type, reading.value, reading.unit)
            self.session.add(
                SensorReading(
                    message_uid=reading.message_id,
                    batch_id=batch.id,
                    device_id=device.id,
                    sensor_id=sensor.id,
                    sensor_type_id=sensor.sensor_type_id,
                    measured_at=reading.measured_at,
                    received_at=now,
                    value=reading.value if assessment.quality != "invalida" else None,
                    unit=reading.unit[:16],
                    quality=assessment.quality,
                    quality_detail=assessment.detail,
                )
            )
            if assessment.quality in ("valida", "sin_dato"):
                outcome.accepted += 1
                status = "aceptada"
            else:
                outcome.invalid += 1
                status = "almacenada_con_observacion"
            outcome.results.append(ReadingOutcome(reading.message_id, status, assessment.quality, assessment.detail))

        batch.accepted_count = outcome.accepted
        batch.invalid_count = outcome.invalid
        batch.rejected_count = outcome.rejected
        batch.duplicate_count = outcome.duplicates
        device.last_seen_at = now
        if firmware_version:
            device.firmware_version = firmware_version[:40]
        try:
            self.session.commit()
        except IntegrityError:
            # Reenvío concurrente del mismo lote o mensaje: se trata como duplicado.
            self.session.rollback()
            previous = self.batches.get_by_uid(device.id, batch_uid)
            if previous is not None:
                return self._duplicate_batch(previous)
            raise
        return outcome

    @staticmethod
    def _duplicate_batch(previous: MeasurementBatch) -> BatchOutcome:
        return BatchOutcome(
            batch_uid=previous.batch_uid,
            status="duplicado",
            received_at=previous.received_at,
            accepted=previous.accepted_count,
            invalid=previous.invalid_count,
            rejected=previous.rejected_count,
            duplicates=previous.duplicate_count,
        )
