"""Resumen y gráficos de los reportes: misma información en la web, el Excel y el PDF."""

import io

import pytest
from openpyxl import load_workbook

from app.business.services.report_charts import add_charts
from app.business.services.report_renderers import Report, render_pdf
from tests.test_iot import BATCH, batch, headers, reading, station  # noqa: F401
from tests.test_reports import with_data  # noqa: F401

CHARTS = "/api/v1/reports/charts"
EXPORT = "/api/v1/reports/export"
ALL_KINDS = [
    "volumen",
    "mediciones",
    "dispositivos",
    "inventario_stock",
    "inventario_movimientos",
    "inventario_consumo",
    "mantenimientos",
    "incidencias",
    "usuarios",
    "auditoria",
]


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_every_report_has_summary_and_charts(admin_client, kind):
    data = admin_client.get(CHARTS, params={"report": kind}).json()
    assert data["summary"] and data["charts"], data
    for chart in data["charts"]:
        assert all(len(s["values"]) == len(chart["categories"]) for s in chart["series"])
    assert admin_client.get(EXPORT, params={"report": kind, "format": "pdf"}).status_code == 200


def test_volume_chart_matches_the_exported_detail(admin_client, with_data):  # noqa: F811
    params = {"report": "volumen", "bucket": "month"}
    chart = admin_client.get(CHARTS, params=params).json()
    assert sum(v for v in chart["charts"][0]["series"][0]["values"] if v) == pytest.approx(4.0)
    assert chart["summary"][0] == {"label": "Total captado", "value": "4 L"}

    wb = load_workbook(io.BytesIO(admin_client.get(EXPORT, params={**params, "format": "xlsx"}).content))
    assert wb.sheetnames == ["Resumen y gráficos", "Detalle"]
    summary = wb["Resumen y gráficos"]
    assert len(summary._charts) == 1  # gráfico nativo de Excel, no una imagen
    assert ("Total captado", "4 L") in [r[:2] for r in summary.iter_rows(values_only=True)]


def test_charts_respect_permissions_and_required_filters(admin_client, make_client, factory):
    teacher = factory.client_for(make_client(), "doc-graf", ["docente"])
    assert teacher.get(CHARTS, params={"report": "mediciones"}).status_code == 403
    director = factory.client_for(make_client(), "dir-graf", ["director"])
    assert director.get(CHARTS, params={"report": "auditoria"}).status_code == 403
    missing = admin_client.get(CHARTS, params={"report": "variable"})
    assert missing.json()["error"]["code"] == "variable_requerida"


def test_charts_do_not_count_as_an_export(admin_client):
    admin_client.get(CHARTS, params={"report": "mediciones"})
    logs = admin_client.get("/api/v1/admin/audit-logs", params={"action": "reporte.exportar"}).json()
    assert logs["total"] == 0


def test_connection_filter_on_devices_and_report(admin_client, client, station):  # noqa: F811
    assert admin_client.get("/api/v1/devices", params={"connection": "sin_comunicacion"}).json()
    assert admin_client.get("/api/v1/devices", params={"connection": "al_dia"}).json() == []
    client.post(BATCH, json=batch(reading("temp", 10, "C")), headers=headers(station))
    online = admin_client.get("/api/v1/devices", params={"connection": "al_dia"}).json()
    assert [d["code"] for d in online] == ["esp32-01"]
    data = admin_client.get(CHARTS, params={"report": "dispositivos", "connection": "al_dia"}).json()
    assert "Comunicación: Al día" in data["criteria"]
    assert data["summary"][1] == {"label": "Al día", "value": "1"}


def test_pdf_escapes_text_and_handles_empty_charts():
    report = add_charts(
        "mantenimientos",
        Report(
            title="Prueba <&>",
            filename="x",
            columns=[
                "Fecha",
                "Dispositivo",
                "Sensor",
                "Tipo",
                "Descripción",
                "Repuestos",
                "Responsable",
                "Estado final",
                "Reporte de incidencia",
            ],
            rows=[[None, "D<1>", None, "calibracion", "a & b", None, "Ana", "operativo", None]],
        ),
    )
    assert report.charts[0].categories == ["Calibración"]
    assert render_pdf(report).content.startswith(b"%PDF")
    empty = add_charts("mantenimientos", Report("Vacío", "x", report.columns, []))
    assert render_pdf(empty).content.startswith(b"%PDF")


def test_analysis_report_matches_the_analysis_module(admin_client, with_data):  # noqa: F811
    analysis = admin_client.get("/api/v1/analysis").json()
    data = admin_client.get(CHARTS, params={"report": "analisis"}).json()
    assert data["summary"][0]["label"] == "Volumen total captado"
    assert analysis["capture"]["total"] == pytest.approx(4.0)
    assert "Volumen captado por día" in [c["title"] for c in data["charts"]]
    for fmt in ("pdf", "xlsx", "csv"):
        assert admin_client.get(EXPORT, params={"report": "analisis", "format": fmt}).status_code == 200
    wb = load_workbook(io.BytesIO(admin_client.get(EXPORT, params={"report": "analisis", "format": "xlsx"}).content))
    rows = list(wb["Detalle"].iter_rows(values_only=True))
    assert ("Captación de agua", "Volumen total captado", 4, "L", None) in rows


def test_analysis_report_only_includes_permitted_sections(make_client, factory):
    director = factory.client_for(make_client(), "dir-anal", ["director"])
    sections = {r[0] for r in _detail(director)}
    assert "Captación de agua" in sections


def _detail(client):
    response = client.get(EXPORT, params={"report": "analisis", "format": "xlsx"})
    assert response.status_code == 200, response.text
    return [r for r in load_workbook(io.BytesIO(response.content))["Detalle"].iter_rows(values_only=True) if r[1]]
