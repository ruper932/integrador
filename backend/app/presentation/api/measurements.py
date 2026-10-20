"""Endpoints de ingesta IoT, históricos y dashboard."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.business.services.ingestion_service import IncomingReading, IngestionService
from app.business.services.measurement_service import MeasurementService
from app.core.permissions import Permission
from app.presentation.api.deps import AuthContext, CurrentDevice, DbSession, require
from app.presentation.schemas.common import Page
from app.presentation.schemas.iot import (
    BatchIn,
    BatchResultOut,
    Bucket,
    DashboardSummaryOut,
    DeviceStatusOut,
    LatestValueOut,
    ReadingOut,
    ReadingResultOut,
    SensorTypeOut,
    SeriesOut,
    SeriesPointOut,
    VolumeTotalsOut,
)

router = APIRouter(tags=["Mediciones y dashboard"])

MeasurementsReader = Annotated[AuthContext, Depends(require(Permission.MEASUREMENTS_READ))]
DashboardReader = Annotated[AuthContext, Depends(require(Permission.DASHBOARD_READ))]
Quality = Literal["valida", "sin_dato", "fuera_de_rango", "unidad_invalida", "invalida"]


@router.post(
    "/iot/measurements/batch",
    response_model=BatchResultOut,
    summary="Recepción de lote de mediciones desde un ESP32",
    description=(
        "Requiere las cabeceras X-Device-Id y X-Device-Key. Reenviar el mismo batch_id es seguro (idempotente)."
    ),
)
def receive_batch(payload: BatchIn, db: DbSession, device: CurrentDevice) -> BatchResultOut:
    outcome = IngestionService(db).ingest(
        device,
        batch_uid=payload.batch_id,
        sent_at=payload.sent_at,
        firmware_version=payload.firmware_version,
        readings=[
            IncomingReading(
                message_id=r.message_id,
                sensor_code=r.sensor_code,
                measured_at=r.measured_at,
                value=r.value,
                unit=r.unit,
            )
            for r in payload.readings
        ],
    )
    return BatchResultOut(
        batch_id=outcome.batch_uid,
        status=outcome.status,
        received_at=outcome.received_at,
        accepted=outcome.accepted,
        invalid=outcome.invalid,
        rejected=outcome.rejected,
        duplicates=outcome.duplicates,
        results=[
            ReadingResultOut(message_id=r.message_id, status=r.status, quality=r.quality, detail=r.detail)
            for r in outcome.results
        ],
    )


@router.get("/measurements", response_model=Page[ReadingOut])
def list_measurements(
    db: DbSession,
    _: MeasurementsReader,
    device_id: int | None = None,
    sensor_id: int | None = None,
    sensor_type: str | None = Query(default=None, description="Código del tipo de sensor"),
    fog_collector_id: int | None = None,
    quality: Quality | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> Page[ReadingOut]:
    items, total = MeasurementService(db).search(
        offset=offset,
        limit=limit,
        device_id=device_id,
        sensor_id=sensor_id,
        sensor_type_code=sensor_type,
        fog_collector_id=fog_collector_id,
        quality=quality,
        date_from=date_from,
        date_to=date_to,
    )
    return Page(items=[ReadingOut.model_validate(r) for r in items], total=total, offset=offset, limit=limit)


@router.get("/dashboard/summary", response_model=DashboardSummaryOut)
def dashboard_summary(db: DbSession, _: DashboardReader) -> DashboardSummaryOut:
    summary = MeasurementService(db).summary()
    devices = [
        DeviceStatusOut(
            id=s.device.id,
            code=s.device.code,
            name=s.device.name,
            status=s.device.status,
            last_seen_at=s.device.last_seen_at,
            minutes_since_last_seen=s.minutes_since_last_seen,
            is_stale=s.is_stale,
        )
        for s in summary.devices
    ]
    latest = [
        LatestValueOut(
            sensor_id=v.reading.sensor_id,
            sensor_code=v.reading.sensor.code,
            device_id=v.reading.device_id,
            sensor_type_code=v.reading.sensor.sensor_type.code,
            sensor_type_name=v.reading.sensor.sensor_type.name,
            unit=v.reading.unit,
            value=v.reading.value,
            measured_at=v.reading.measured_at,
            is_stale=v.is_stale,
        )
        for v in summary.latest
    ]
    return DashboardSummaryOut(
        generated_at=summary.generated_at,
        stale_threshold_minutes=summary.stale_threshold_minutes,
        last_communication_at=summary.last_communication_at,
        has_stale_data=any(d.is_stale for d in devices) or any(v.is_stale for v in latest),
        devices=devices,
        latest=latest,
        volume=VolumeTotalsOut(
            today_liters=summary.volume.today_liters,
            last_7_days_liters=summary.volume.last_7_days_liters,
            month_liters=summary.volume.month_liters,
        ),
    )


@router.get("/dashboard/series", response_model=SeriesOut)
def dashboard_series(
    db: DbSession,
    _: DashboardReader,
    sensor_type: str = Query(description="Código del tipo de sensor, p. ej. volumen_captado"),
    bucket: Bucket = "day",
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    device_id: int | None = None,
    sensor_id: int | None = None,
    fog_collector_id: int | None = None,
) -> SeriesOut:
    series = MeasurementService(db).series(
        sensor_type_code=sensor_type,
        bucket=bucket,
        date_from=date_from,
        date_to=date_to,
        device_id=device_id,
        sensor_id=sensor_id,
        fog_collector_id=fog_collector_id,
    )
    return SeriesOut(
        sensor_type=SensorTypeOut.model_validate(series.sensor_type),
        aggregation=series.sensor_type.aggregation,
        bucket=bucket,
        date_from=series.date_from,
        date_to=series.date_to,
        points=[
            SeriesPointOut(bucket=p.bucket, value=p.value, min=p.min, max=p.max, count=p.count) for p in series.points
        ],
    )
