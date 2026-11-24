"""Generación de archivos de reporte (CSV, Excel y PDF) en el servidor.

Excel y PDF llevan, además del detalle, el resumen y los gráficos del reporte: en Excel como gráficos
nativos editables (con su tabla de datos al lado) y en PDF como gráficos vectoriales. El CSV contiene
solo los datos, para procesarlos en otra herramienta.
"""

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from xml.sax.saxutils import escape

from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from reportlab.graphics.charts.barcharts import HorizontalBarChart, VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    CondPageBreak,
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

INSTITUTION = "CEA “Ildefonso de las Muñecas” — Titicachi, Chuma, La Paz"
SYSTEM = "Sistema de monitoreo de agua captada mediante atrapanieblas"
MAX_PDF_ROWS = 5000

# Paleta institucional (la misma del sistema web).
INK = "2B4D3B"
SAGE = "B9D2C2"
CREAM = "FBF7F1"
MUTED = "5F6F66"
# Series de los gráficos, en orden fijo (validadas para daltonismo sobre fondo claro).
SERIES_COLORS = ["428C5C", "6A8ED4", "B87A43", "8776BB", "C16D7B"]


@dataclass
class Series:
    name: str
    values: list[float | None]


@dataclass
class Chart:
    """Gráfico derivado de los datos del reporte; se dibuja igual en la web, en Excel y en PDF."""

    title: str
    kind: str  # "bar" o "line"
    categories: list[str]
    series: list[Series]
    unit: str = ""
    horizontal: bool = False  # barras horizontales para categorías con nombres largos


@dataclass
class Report:
    title: str
    filename: str
    columns: list[str]
    rows: list[list[Any]]
    filters: list[str] = field(default_factory=list)
    generated_at: datetime | None = None
    generated_by: str | None = None
    summary: list[tuple[str, str]] = field(default_factory=list)
    charts: list[Chart] = field(default_factory=list)


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


def _generated_line(report: Report) -> str | None:
    if not report.generated_at:
        return None
    by = f" por {report.generated_by}" if report.generated_by else ""
    return f"Generado el {report.generated_at.strftime('%Y-%m-%d %H:%M')}{by}"


def _header_lines(report: Report) -> list[str]:
    lines = [INSTITUTION]
    generated = _generated_line(report)
    if generated:
        lines.append(generated)
    lines.extend(report.filters)
    return lines


# --- CSV ----------------------------------------------------------------------------------------


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


# --- Excel --------------------------------------------------------------------------------------

_HEADER_FONT = Font(bold=True, color="FFFFFF")
_HEADER_FILL = PatternFill("solid", fgColor=INK)
_THIN = Border(bottom=Side(style="thin", color=SAGE))


def _style_header(ws: Worksheet, row: int, count: int) -> None:
    for col in range(1, count + 1):
        cell = ws.cell(row=row, column=col)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(vertical="center", wrap_text=True)


def _write_heading(ws: Worksheet, report: Report) -> None:
    ws.append([report.title])
    ws["A1"].font = Font(bold=True, size=14, color=INK)
    ws.append([SYSTEM])
    ws["A2"].font = Font(color=MUTED)
    for line in _header_lines(report):
        ws.append([line])
    ws.append([])


def _excel_chart(chart: Chart, ws: Worksheet, header_row: int) -> BarChart | LineChart:
    n = len(chart.categories)
    if chart.kind == "line":
        xl: BarChart | LineChart = LineChart()
    else:
        xl = BarChart()
        xl.type = "bar" if chart.horizontal else "col"
        xl.gapWidth = 60
    xl.title = chart.title
    xl.y_axis.title = chart.unit or None
    xl.width, xl.height = 22, 9
    data = Reference(ws, min_col=2, max_col=1 + len(chart.series), min_row=header_row, max_row=header_row + n)
    xl.add_data(data, titles_from_data=True)
    xl.set_categories(Reference(ws, min_col=1, min_row=header_row + 1, max_row=header_row + n))
    for index, series in enumerate(xl.series):
        color = SERIES_COLORS[index % len(SERIES_COLORS)]
        if chart.kind == "line":
            series.graphicalProperties.line.solidFill = color
            series.graphicalProperties.line.width = 22000
            series.smooth = False
        else:
            series.graphicalProperties.solidFill = color
            series.graphicalProperties.line.noFill = True
    if len(chart.series) == 1:
        xl.legend = None
    else:
        xl.legend.position = "t"
    # Sin esto, versiones recientes de Excel ocultan los ejes.
    xl.x_axis.delete = False
    xl.y_axis.delete = False
    return xl


def _write_summary_sheet(ws: Worksheet, report: Report) -> None:
    _write_heading(ws, report)
    if report.summary:
        ws.append(["Resumen"])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12, color=INK)
        start = ws.max_row + 1
        ws.append(["Indicador", "Valor"])
        _style_header(ws, start, 2)
        for label, value in report.summary:
            ws.append([label, value])
            ws.cell(row=ws.max_row, column=1).border = _THIN
            ws.cell(row=ws.max_row, column=2).border = _THIN
        ws.append([])
    for number, chart in enumerate(report.charts, start=1):
        ws.append([f"Figura {number}. {chart.title}"])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=12, color=INK)
        header_row = ws.max_row + 1
        ws.append(["Categoría", *[s.name for s in chart.series]])
        _style_header(ws, header_row, 1 + len(chart.series))
        for index, category in enumerate(chart.categories):
            ws.append([category, *[s.values[index] for s in chart.series]])
        if chart.categories:
            # El gráfico va a la derecha de su tabla de datos, alineado con ella.
            anchor_col = get_column_letter(len(chart.series) + 3)
            ws.add_chart(_excel_chart(chart, ws, header_row), f"{anchor_col}{header_row}")
        # Deja lugar para el alto del gráfico (~18 filas) antes del siguiente.
        used = len(chart.categories) + 1
        for _ in range(max(used, 19) - used + 2):
            ws.append([])
    ws.column_dimensions["A"].width = 34
    for col in range(2, 7):
        ws.column_dimensions[get_column_letter(col)].width = 16


def _write_detail_sheet(ws: Worksheet, report: Report) -> None:
    _write_heading(ws, report)
    header_row = ws.max_row + 1
    ws.append(report.columns)
    _style_header(ws, header_row, len(report.columns))
    for row in report.rows:
        ws.append([v.replace(tzinfo=None) if isinstance(v, datetime) else v for v in row])
    for index, column in enumerate(report.columns, start=1):
        width = max([len(column)] + [len(_text(r[index - 1])) for r in report.rows[:500]])
        ws.column_dimensions[get_column_letter(index)].width = min(max(10, width + 2), 60)
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    ws.auto_filter.ref = f"A{header_row}:{get_column_letter(len(report.columns))}{ws.max_row}"


def render_xlsx(report: Report) -> RenderedFile:
    wb = Workbook()
    detail = wb.active
    detail.title = "Detalle"
    if report.summary or report.charts:
        summary = wb.create_sheet("Resumen y gráficos", 0)
        _write_summary_sheet(summary, report)
        wb.active = 0
    _write_detail_sheet(detail, report)
    for ws in wb.worksheets:
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
    buffer = io.BytesIO()
    wb.save(buffer)
    return RenderedFile(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"{report.filename}.xlsx",
    )


# --- PDF ----------------------------------------------------------------------------------------


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


def _hex(value: str) -> colors.Color:
    return colors.HexColor(f"#{value}")


def _axis_number(value: float) -> str:
    if abs(value) >= 1000:  # noqa: PLR2004 - miles con separador
        return f"{value:,.0f}".replace(",", ".")
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _thin_labels(categories: list[str], keep: int) -> list[str]:
    """Con muchas categorías se rotula solo una de cada k para que las etiquetas no se encimen."""
    if len(categories) <= keep:
        return categories
    step = -(-len(categories) // keep)
    return [c if i % step == 0 else "" for i, c in enumerate(categories)]


def _pdf_chart(chart: Chart, width: float) -> Drawing:
    n = len(chart.categories)
    horizontal = chart.kind == "bar" and chart.horizontal
    height = max(170.0, min(14.0 * n + 50, 330.0)) if horizontal else 210.0
    drawing = Drawing(width, height)
    legend_room = 18 if len(chart.series) > 1 else 0
    data = [tuple(s.values) for s in chart.series]
    if chart.kind == "line":
        plot: Any = HorizontalLineChart()
    elif horizontal:
        plot = HorizontalBarChart()
    else:
        plot = VerticalBarChart()
    longest = max((len(c) for c in chart.categories), default=0)
    rotate = not horizontal and (n > 8 or longest > 10)  # noqa: PLR2004
    if horizontal:
        left = min(max(longest * 4.6, 50), width * 0.4)
        plot.x, plot.y = left + 8, 22
        plot.width, plot.height = width - left - 24, height - 34 - legend_room
    else:
        bottom = 58 if rotate else 30
        plot.x, plot.y = 46, bottom
        plot.width, plot.height = width - 60, height - bottom - 12 - legend_room
    plot.data = data
    plot.categoryAxis.categoryNames = chart.categories if horizontal else _thin_labels(chart.categories, 24)
    plot.categoryAxis.labels.fontSize = 7
    plot.categoryAxis.labels.fontName = "Helvetica"
    plot.categoryAxis.strokeColor = _hex(MUTED)
    if horizontal:
        plot.categoryAxis.labels.boxAnchor = "e"
        plot.categoryAxis.labels.dx = -4
        plot.categoryAxis.reverseDirection = True  # la primera categoría arriba
    elif rotate:
        plot.categoryAxis.labels.angle = 45
        plot.categoryAxis.labels.boxAnchor = "ne"
        plot.categoryAxis.labels.dy = -2
    plot.valueAxis.labels.fontSize = 7
    plot.valueAxis.labelTextFormat = _axis_number
    plot.valueAxis.strokeColor = _hex(MUTED)
    plot.valueAxis.visibleGrid = True
    plot.valueAxis.gridStrokeColor = colors.HexColor("#E3E7E4")
    plot.valueAxis.gridStrokeWidth = 0.4
    numbers = [v for s in chart.series for v in s.values if v is not None]
    if chart.kind == "bar" or (numbers and min(numbers) >= 0):
        plot.valueAxis.valueMin = min(0, min(numbers, default=0))
    if not numbers:
        plot.valueAxis.valueMin, plot.valueAxis.valueMax = 0, 1
    for index in range(len(chart.series)):
        color = _hex(SERIES_COLORS[index % len(SERIES_COLORS)])
        if chart.kind == "line":
            plot.lines[index].strokeColor = color
            plot.lines[index].strokeWidth = 1.6
        else:
            plot.bars[index].fillColor = color
            plot.bars[index].strokeColor = None
    if chart.kind == "bar":
        plot.groupSpacing = 4 if n > 20 else 8  # noqa: PLR2004
        plot.barSpacing = 1
    drawing.add(plot)
    if len(chart.series) > 1:
        legend = Legend()
        legend.x, legend.y = plot.x, height - 6
        legend.alignment = "right"
        legend.columnMaximum = 1
        legend.deltax = 110
        legend.dx, legend.dy = 8, 8
        legend.fontName, legend.fontSize = "Helvetica", 8
        legend.colorNamePairs = [
            (_hex(SERIES_COLORS[i % len(SERIES_COLORS)]), s.name) for i, s in enumerate(chart.series)
        ]
        drawing.add(legend)
    return drawing


def _numbered_canvas(report: Report) -> type[canvas.Canvas]:
    """Canvas que agrega a cada página el pie institucional con «Página X de Y»."""

    class NumberedCanvas(canvas.Canvas):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._pages: list[dict[str, Any]] = []

        def showPage(self) -> None:  # noqa: N802 - nombre de la API de ReportLab
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self) -> None:
            total = len(self._pages)
            for state in self._pages:
                self.__dict__.update(state)
                self._footer(total)
                super().showPage()
            super().save()

        def _footer(self, total: int) -> None:
            width, _ = self._pagesize
            margin = 1.5 * cm
            self.saveState()
            self.setStrokeColor(_hex(SAGE))
            self.setLineWidth(0.6)
            self.line(margin, 1.15 * cm, width - margin, 1.15 * cm)
            self.setFont("Helvetica", 7.5)
            self.setFillColor(_hex(MUTED))
            self.drawString(margin, 0.75 * cm, f"{INSTITUTION} · {report.title}"[:150])
            self.drawRightString(width - margin, 0.75 * cm, f"Página {self._pageNumber} de {total}")
            self.restoreState()

    return NumberedCanvas


def render_pdf(report: Report) -> RenderedFile:  # noqa: PLR0915 - arma el documento sección por sección
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.7 * cm,
        title=report.title,
        author=INSTITUTION,
        subject=SYSTEM,
    )
    base = getSampleStyleSheet()
    ink, muted = _hex(INK), _hex(MUTED)
    institution = ParagraphStyle("inst", parent=base["Normal"], fontSize=9, textColor=ink, fontName="Helvetica-Bold")
    system = ParagraphStyle("sys", parent=base["Normal"], fontSize=8.5, textColor=muted)
    title = ParagraphStyle(
        "title", parent=base["Title"], fontSize=18, leading=22, textColor=ink, alignment=0, spaceBefore=6, spaceAfter=4
    )
    section = ParagraphStyle(
        "section", parent=base["Heading2"], fontSize=12, textColor=ink, spaceBefore=10, spaceAfter=6
    )
    caption = ParagraphStyle(
        "caption", parent=base["Normal"], fontSize=9, leading=12, textColor=ink, spaceBefore=4, spaceAfter=4
    )
    note = ParagraphStyle("note", parent=base["Normal"], fontSize=8, leading=10, textColor=muted)
    meta = ParagraphStyle("meta", parent=base["Normal"], fontSize=8.5, leading=11)
    right = ParagraphStyle("right", parent=meta, alignment=TA_RIGHT, textColor=muted)

    story: list[Any] = [
        Table(
            [[Paragraph(escape(INSTITUTION), institution), Paragraph(escape(_generated_line(report) or ""), right)]],
            colWidths=[doc.width * 0.6, doc.width * 0.4],
            style=TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]),
        ),
        Paragraph(SYSTEM, system),
        Paragraph(escape(report.title), title),
        HRFlowable(width="100%", thickness=1.2, color=ink, spaceBefore=2, spaceAfter=8),
    ]

    sections = 0

    def heading(text: str) -> Paragraph:
        nonlocal sections
        sections += 1
        return Paragraph(f"{sections}. {text}", section)

    story.append(heading("Criterios del reporte"))
    story += [Paragraph(f"• {escape(line)}", meta) for line in report.filters]
    story.append(Paragraph(f"• Registros incluidos: {len(report.rows)}", meta))

    if report.summary:
        story.append(heading("Resumen"))
        per_row = 4
        cells = [
            Paragraph(
                f'<font size="7.5" color="#{MUTED}">{escape(label)}</font><br/>'
                f'<font size="12"><b>{escape(value)}</b></font>',
                meta,
            )
            for label, value in report.summary
        ]
        cells += [""] * (-len(cells) % per_row)
        grid = [cells[i : i + per_row] for i in range(0, len(cells), per_row)]
        kpis = Table(grid, colWidths=[doc.width / per_row] * per_row)
        kpis.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), _hex(CREAM)),
                    ("LINEABOVE", (0, 0), (-1, 0), 1.2, _hex(SAGE)),
                    ("LINEBELOW", (0, -1), (-1, -1), 1.2, _hex(SAGE)),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(kpis)

    if report.charts:
        story.append(heading("Gráficos"))
        for number, chart in enumerate(report.charts, start=1):
            block: list[Any] = [Paragraph(f"<b>Figura {number}.</b> <i>{escape(chart.title)}</i>", caption)]
            if chart.categories:
                block.append(_pdf_chart(chart, doc.width))
                if chart.unit:
                    block.append(Paragraph(f"<i>Nota.</i> Unidad: {escape(chart.unit)}.", note))
            else:
                block.append(Paragraph("Sin datos para graficar con los filtros seleccionados.", note))
            block.append(Spacer(1, 0.3 * cm))
            story.append(KeepTogether(block))

    story.append(CondPageBreak(5 * cm))
    story.append(heading("Detalle de registros"))
    size = 7 if len(report.columns) > 11 else 8  # noqa: PLR2004 - letra menor si hay muchas columnas
    cell_style = base["BodyText"].clone("cell", fontSize=size, leading=size + 2)
    head_style = cell_style.clone("head", textColor=colors.white, fontName="Helvetica-Bold")
    rows = report.rows[:MAX_PDF_ROWS]
    data = [[Paragraph(escape(c), head_style) for c in report.columns]]
    data += [[Paragraph(escape(_text(v)), cell_style) for v in row] for row in rows]
    if not rows:
        data.append(
            [Paragraph("Sin datos para los filtros seleccionados.", cell_style)] + [""] * (len(report.columns) - 1)
        )
    story.append(Paragraph(f"<b>Tabla 1.</b> <i>{escape(report.title)}</i>", caption))
    table = Table(data, repeatRows=1, colWidths=_column_widths(report, rows, doc.width, size))
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ink),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, _hex(SAGE)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _hex(CREAM)]),
            ]
        )
    )
    story.append(table)
    if len(report.rows) > MAX_PDF_ROWS:
        story.append(Spacer(1, 0.3 * cm))
        story.append(
            Paragraph(
                f"Se muestran {MAX_PDF_ROWS} de {len(report.rows)} filas. Use Excel o CSV para el detalle completo.",
                note,
            )
        )
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("Fin del reporte.", note))
    doc.build(story, canvasmaker=_numbered_canvas(report))
    return RenderedFile(content=buffer.getvalue(), media_type="application/pdf", filename=f"{report.filename}.pdf")


RENDERERS = {"csv": render_csv, "xlsx": render_xlsx, "pdf": render_pdf}
