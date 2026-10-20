"""Generación de archivos de reporte (CSV, Excel y PDF) en el servidor."""

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

INSTITUTION = "CEA “Ildefonso de las Muñecas” — Titicachi, Chuma, La Paz"
MAX_PDF_ROWS = 5000


@dataclass
class Report:
    title: str
    filename: str
    columns: list[str]
    rows: list[list[Any]]
    filters: list[str] = field(default_factory=list)
    generated_at: datetime | None = None
    generated_by: str | None = None


@dataclass(frozen=True)
class RenderedFile:
    content: bytes
    media_type: str
    filename: str


def _text(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def _header_lines(report: Report) -> list[str]:
    lines = [INSTITUTION]
    if report.generated_at:
        by = f" por {report.generated_by}" if report.generated_by else ""
        lines.append(f"Generado el {report.generated_at.strftime('%Y-%m-%d %H:%M')}{by}")
    lines.extend(report.filters)
    return lines


def render_csv(report: Report) -> RenderedFile:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(report.columns)
    # Los valores no medidos quedan vacíos (no como 0).
    writer.writerows([["" if v is None else _text(v) for v in row] for row in report.rows])
    return RenderedFile(
        content=("﻿" + buffer.getvalue()).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        filename=f"{report.filename}.csv",
    )


def render_xlsx(report: Report) -> RenderedFile:
    wb = Workbook()
    ws = wb.active
    ws.title = report.title[:31]
    ws.append([report.title])
    ws["A1"].font = Font(bold=True, size=14)
    for line in _header_lines(report):
        ws.append([line])
    ws.append([])
    header_row = ws.max_row + 1
    ws.append(report.columns)
    for cell in ws[header_row]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="2C2C26")
    for row in report.rows:
        ws.append([v.replace(tzinfo=None) if isinstance(v, datetime) else v for v in row])
    for index, column in enumerate(report.columns, start=1):
        width = max([len(column)] + [len(_text(r[index - 1])) for r in report.rows[:500]])
        ws.column_dimensions[get_column_letter(index)].width = min(max(10, width + 2), 60)
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    buffer = io.BytesIO()
    wb.save(buffer)
    return RenderedFile(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"{report.filename}.xlsx",
    )


def _column_widths(report: Report, rows: list[list[Any]], available: float, font_size: float) -> list[float]:
    """Ancho de columnas según el contenido.

    Cada columna recibe al menos el ancho de la palabra más larga de su encabezado y de sus valores
    (hasta un límite), para que no se corten palabras; el espacio restante se reparte según la
    longitud media del texto, de modo que las descripciones reciben más espacio.
    """
    char = font_size * 0.6  # ancho aproximado de un carácter (Helvetica)
    padding = 8.0
    minimums: list[float] = []
    weights: list[float] = []
    for index, column in enumerate(report.columns):
        texts = [_text(r[index]) for r in rows[:200]]
        words = [w for t in [column, *texts] for w in t.split()]
        longest = min(max((len(w) for w in words), default=4), 16)
        minimums.append(longest * char + padding)
        weights.append(sum(len(t) for t in texts) / len(texts) if texts else len(column))
    base = sum(minimums)
    if base >= available:
        return [available * m / base for m in minimums]
    extra = available - base
    total = sum(weights) or 1.0
    return [m + extra * w / total for m, w in zip(minimums, weights, strict=True)]


def render_pdf(report: Report) -> RenderedFile:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=report.title,
    )
    styles = getSampleStyleSheet()
    # Los reportes con muchas columnas usan una letra algo menor para que quepan en la página.
    size = 7 if len(report.columns) > 11 else 8
    cell_style = styles["BodyText"].clone("cell", fontSize=size, leading=size + 2)
    story: list[Any] = [Paragraph(report.title, styles["Title"])]
    story += [Paragraph(line, styles["Normal"]) for line in _header_lines(report)]
    story.append(Spacer(1, 0.4 * cm))

    rows = report.rows[:MAX_PDF_ROWS]
    data = [[Paragraph(f"<b>{c}</b>", cell_style) for c in report.columns]]
    data += [[Paragraph(_text(v), cell_style) for v in row] for row in rows]
    if not rows:
        data.append(
            [Paragraph("Sin datos para los filtros seleccionados.", cell_style)] + [""] * (len(report.columns) - 1)
        )
    table = Table(data, repeatRows=1, colWidths=_column_widths(report, rows, doc.width, size))
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8E7D9")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D0D0C8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F6F4")]),
            ]
        )
    )
    story.append(table)
    if len(report.rows) > MAX_PDF_ROWS:
        story.append(Spacer(1, 0.3 * cm))
        story.append(
            Paragraph(
                f"Se muestran {MAX_PDF_ROWS} de {len(report.rows)} filas. Use Excel o CSV para el detalle completo.",
                styles["Italic"],
            )
        )
    doc.build(story)
    return RenderedFile(content=buffer.getvalue(), media_type="application/pdf", filename=f"{report.filename}.pdf")


RENDERERS = {"csv": render_csv, "xlsx": render_xlsx, "pdf": render_pdf}
