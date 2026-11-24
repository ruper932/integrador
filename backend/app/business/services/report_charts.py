"""Resumen e indicadores gráficos de cada reporte.

Se calculan a partir de las mismas filas del reporte, de modo que lo que se ve en la web, en el Excel
y en el PDF coincide siempre con el detalle exportado.
"""

from collections import Counter
from collections.abc import Callable, Iterable
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.business.services.report_renderers import Chart, Report, Series

TOP = 12  # categorías por gráfico; el resto se agrupa en «Otros»
# Códigos guardados sin tilde o abreviados, con su nombre para el lector.
LABELS = {
    "valida": "Válida",
    "invalida": "Inválida",
    "unidad_invalida": "Unidad inválida",
    "calibracion": "Calibración",
    "inspeccion": "Inspección",
    "mantenimiento": "En mantenimiento",
}


def _col(report: Report, prefix: str) -> int:
    return next(i for i, c in enumerate(report.columns) if c.startswith(prefix))


def _values(report: Report, prefix: str) -> list[Any]:
    index = _col(report, prefix)
    return [row[index] for row in report.rows]


def _num(value: Any) -> float | None:
    if value is None:
        return None
    return float(value) if isinstance(value, (int, float, Decimal)) else None


def _fmt(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return "—"
    text = f"{value:,.{decimals}f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return text.rstrip("0").rstrip(",") if decimals else text


def _label(value: Any) -> str:
    if value is None or value == "":
        return "Sin dato"
    if str(value) in LABELS:
        return LABELS[str(value)]
    text = str(value).replace("_", " ")
    return text[:1].upper() + text[1:]


def _counts(
    title: str, values: Iterable[Any], unit: str, *, order: list[str] | None = None, horizontal: bool = False
) -> Chart:
    counter = Counter(_label(v) for v in values)
    if order:
        ranked = [(k, counter[k]) for k in order if counter[k]] + [
            (k, n) for k, n in counter.most_common() if k not in order
        ]
    else:
        ranked = counter.most_common()
    if len(ranked) > TOP:
        rest = sum(n for _, n in ranked[TOP - 1 :])
        ranked = [*ranked[: TOP - 1], ("Otros", rest)]
    return Chart(
        title=title,
        kind="bar",
        categories=[k for k, _ in ranked],
        series=[Series(unit[:1].upper() + unit[1:], [float(n) for _, n in ranked])],
        unit=unit,
        horizontal=horizontal or any(len(k) > 14 for k, _ in ranked),  # noqa: PLR2004
    )


def _period(value: Any, bucket: str) -> str:
    if not isinstance(value, (datetime, date)):
        return _label(value)
    return {
        "hora": value.strftime("%d/%m %H:%M"),
        "semana": f"Sem. {value:%d/%m/%Y}",
        "mes": value.strftime("%m/%Y"),
    }.get(bucket, value.strftime("%d/%m/%Y"))


def _day(value: Any) -> str:
    return value.strftime("%d/%m/%Y") if isinstance(value, datetime) else _label(value)


def _by_day(title: str, report: Report, prefix: str, unit: str) -> Chart:
    """Cantidad de registros por día, en orden cronológico."""
    counter = Counter(v.date() for v in _values(report, prefix) if isinstance(v, datetime))
    days = sorted(counter)
    return Chart(
        title=title,
        kind="bar",
        categories=[d.strftime("%d/%m/%Y") for d in days],
        series=[Series(unit[:1].upper() + unit[1:], [float(counter[d]) for d in days])],
        unit=unit,
    )


# --- Monitoreo -----------------------------------------------------------------------------------


def _series(report: Report) -> None:
    bucket = report.columns[0].removeprefix("Periodo (").removesuffix(")")
    value_col = report.columns[1]
    unit = value_col[value_col.find("(") + 1 : -1]
    incremental = value_col.startswith("Total")
    rows = report.rows
    categories = [_period(r[0], bucket) for r in rows]
    values = [_num(r[1]) for r in rows]
    counts = sum(int(r[4] or 0) for r in rows)
    measured = [v for v in values if v is not None]
    if incremental:
        best = max(((v, c) for v, c in zip(values, categories, strict=True) if v is not None), default=None)
        report.summary = [
            ("Total captado", f"{_fmt(sum(measured))} {unit}"),
            (f"Promedio por {bucket}", f"{_fmt(sum(measured) / len(measured)) if measured else '—'} {unit}"),
            (f"{bucket.capitalize()} de mayor captación", f"{best[1]} ({_fmt(best[0])} {unit})" if best else "—"),
            ("Lecturas válidas", _fmt(counts, 0)),
        ]
        report.charts = [Chart(f"{report.title} por {bucket}", "bar", categories, [Series(value_col, values)], unit)]
        return
    lows = [v for v in (_num(r[2]) for r in rows) if v is not None]
    highs = [v for v in (_num(r[3]) for r in rows) if v is not None]
    weighted = sum((_num(r[1]) or 0) * int(r[4] or 0) for r in rows if r[1] is not None)
    weights = sum(int(r[4] or 0) for r in rows if r[1] is not None)
    report.summary = [
        ("Promedio del periodo", f"{_fmt(weighted / weights) if weights else '—'} {unit}"),
        ("Mínimo registrado", f"{_fmt(min(lows)) if lows else '—'} {unit}"),
        ("Máximo registrado", f"{_fmt(max(highs)) if highs else '—'} {unit}"),
        ("Lecturas válidas", _fmt(counts, 0)),
    ]
    report.charts = [
        Chart(
            f"Promedio, mínimo y máximo por {bucket}",
            "line",
            categories,
            [
                Series("Promedio", values),
                Series("Mínimo", [_num(r[2]) for r in rows]),
                Series("Máximo", [_num(r[3]) for r in rows]),
            ],
            unit,
        )
    ]


def _mediciones(report: Report) -> None:
    quality = _values(report, "Calidad")
    valid = sum(1 for q in quality if q == "valida")
    report.summary = [
        ("Lecturas", _fmt(len(quality), 0)),
        ("Lecturas válidas", f"{_fmt(valid, 0)} ({_fmt(100 * valid / len(quality), 1) if quality else '0'} %)"),
        ("Dispositivos", _fmt(len(set(_values(report, "Dispositivo"))), 0)),
        ("Variables", _fmt(len(set(_values(report, "Variable"))), 0)),
    ]
    report.charts = [
        _counts("Lecturas por calidad", quality, "lecturas"),
        _counts("Lecturas por variable", _values(report, "Variable"), "lecturas", horizontal=True),
    ]


def _dispositivos(report: Report) -> None:
    situation = _values(report, "Situación")
    report.summary = [
        ("Estaciones", _fmt(len(situation), 0)),
        ("Al día", _fmt(situation.count("Al día"), 0)),
        ("Desactualizadas o sin comunicación", _fmt(len(situation) - situation.count("Al día"), 0)),
        ("Sensores activos", _fmt(sum(int(v or 0) for v in _values(report, "Sensores activos")), 0)),
    ]
    report.charts = [
        _counts(
            "Estaciones según su comunicación",
            situation,
            "estaciones",
            order=["Al día", "Desactualizado", "Sin comunicación"],
        ),
        _counts(
            "Estaciones según su estado",
            _values(report, "Estado"),
            "estaciones",
            order=["Activo", "En mantenimiento", "Inactivo"],
        ),
    ]


# --- Inventario ----------------------------------------------------------------------------------


def _inventario_stock(report: Report) -> None:
    rows = report.rows
    code, name, stock, minimum, repo = (
        _col(report, "Código"),
        _col(report, "Nombre"),
        _col(report, "Stock actual"),
        _col(report, "Stock mínimo"),
        _col(report, "Reposición"),
    )
    low = [r for r in rows if r[repo] == "Sí"]
    focus = sorted(low or rows, key=lambda r: (_num(r[stock]) or 0) - (_num(r[minimum]) or 0))[:TOP]
    report.summary = [
        ("Repuestos", _fmt(len(rows), 0)),
        ("Requieren reposición", _fmt(len(low), 0)),
        ("Categorías", _fmt(len(set(_values(report, "Categoría"))), 0)),
    ]
    report.charts = [
        Chart(
            "Repuestos con stock bajo: actual frente al mínimo" if low else "Repuestos más cercanos al stock mínimo",
            "bar",
            [f"{r[code]} {r[name]}"[:40] for r in focus],
            [
                Series("Stock actual", [_num(r[stock]) for r in focus]),
                Series("Stock mínimo", [_num(r[minimum]) for r in focus]),
            ],
            "la unidad de cada repuesto",
            horizontal=True,
        ),
        _counts("Repuestos por categoría", _values(report, "Categoría"), "repuestos", horizontal=True),
    ]


def _inventario_movimientos(report: Report) -> None:
    types = _values(report, "Tipo")
    report.summary = [
        ("Movimientos", _fmt(len(types), 0)),
        ("Repuestos distintos", _fmt(len(set(_values(report, "Código"))), 0)),
        ("Usuarios que registraron", _fmt(len(set(_values(report, "Usuario"))), 0)),
    ]
    report.charts = [
        _counts("Movimientos por tipo", types, "movimientos", horizontal=True),
        _by_day("Movimientos por día", report, "Fecha efectiva", "movimientos"),
    ]


def _inventario_periodo(report: Report) -> None:
    rows = [r for r in report.rows if r[0] != "TOTAL"]
    total = next((r[-1] for r in report.rows if r[0] == "TOTAL"), None)
    entries, exits, maint = _col(report, "Entradas"), _col(report, "Salidas"), _col(report, "Salidas por mant")
    value = _col(report, "Valor final")
    active = sorted(rows, key=lambda r: -((_num(r[entries]) or 0) + (_num(r[exits]) or 0)))[:TOP]
    valued = sorted((r for r in rows if _num(r[value])), key=lambda r: -(_num(r[value]) or 0))[:TOP]
    report.summary = [
        ("Repuestos", _fmt(len(rows), 0)),
        ("Con movimientos", _fmt(sum(1 for r in rows if _num(r[entries]) or _num(r[exits])), 0)),
        ("Valor final del inventario", f"Bs {_fmt(_num(total))}" if total is not None else "Sin costo completo"),
    ]
    report.charts = [
        Chart(
            "Entradas y salidas por repuesto",
            "bar",
            [f"{r[0]} {r[1]}"[:40] for r in active],
            [
                Series("Entradas", [_num(r[entries]) for r in active]),
                Series("Salidas", [_num(r[exits]) for r in active]),
                Series("Salidas por mantenimiento", [_num(r[maint]) for r in active]),
            ],
            "la unidad de cada repuesto",
            horizontal=True,
        ),
        Chart(
            "Valor final por repuesto",
            "bar",
            [f"{r[0]} {r[1]}"[:40] for r in valued],
            [Series("Valor final (Bs)", [_num(r[value]) for r in valued])],
            "bolivianos (Bs)",
            horizontal=True,
        ),
    ]


def _inventario_conteo(report: Report) -> None:
    diff = _col(report, "Diferencia")
    counted = [r for r in report.rows if r[_col(report, "Cantidad contada")] is not None]
    differing = sorted((r for r in report.rows if _num(r[diff])), key=lambda r: _num(r[diff]) or 0)[: TOP * 2]
    report.summary = [
        ("Repuestos", _fmt(len(report.rows), 0)),
        ("Contados", _fmt(len(counted), 0)),
        ("Con sobrante", _fmt(sum(1 for r in report.rows if (_num(r[diff]) or 0) > 0), 0)),
        ("Con faltante", _fmt(sum(1 for r in report.rows if (_num(r[diff]) or 0) < 0), 0)),
    ]
    report.charts = [
        Chart(
            "Diferencias entre lo contado y los registros",
            "bar",
            [f"{r[0]} {r[1]}"[:40] for r in differing],
            [Series("Diferencia", [_num(r[diff]) for r in differing])],
            "la unidad de cada repuesto (positivo: sobrante; negativo: faltante)",
            horizontal=True,
        )
    ]


def _inventario_kardex(report: Report) -> None:
    rows = report.rows
    unit = report.columns[_col(report, "Saldo")].split("(")[-1].rstrip(")")
    entries = sum(_num(r[_col(report, "Entrada")]) or 0 for r in rows)
    exits = sum(_num(r[_col(report, "Salida")]) or 0 for r in rows)
    balance = _col(report, "Saldo")
    report.summary = [
        ("Saldo inicial", f"{_fmt(_num(rows[0][balance]))} {unit}" if rows else "—"),
        ("Entradas", f"{_fmt(entries)} {unit}"),
        ("Salidas", f"{_fmt(exits)} {unit}"),
        ("Saldo final", f"{_fmt(_num(rows[-1][balance]))} {unit}" if rows else "—"),
    ]
    report.charts = [
        Chart(
            "Evolución del saldo",
            "line",
            [_day(r[0]) for r in rows],
            [Series(f"Saldo ({unit})", [_num(r[balance]) for r in rows])],
            unit,
        )
    ]


def _inventario_consumo(report: Report) -> None:
    code, name, qty = _col(report, "Código"), _col(report, "Repuesto"), _col(report, "Cantidad utilizada")
    totals: Counter[str] = Counter()
    for r in report.rows:
        totals[f"{r[code]} {r[name]}"[:40]] += _num(r[qty]) or 0
    top = totals.most_common(TOP)
    report.summary = [
        ("Repuestos utilizados", _fmt(len(totals), 0)),
        ("Dispositivos atendidos", _fmt(len(set(_values(report, "Dispositivo"))), 0)),
    ]
    report.charts = [
        Chart(
            "Repuestos más utilizados",
            "bar",
            [k for k, _ in top],
            [Series("Cantidad utilizada", [v for _, v in top])],
            "la unidad de cada repuesto",
            horizontal=True,
        ),
        _counts("Líneas de consumo por dispositivo", _values(report, "Dispositivo"), "repuestos distintos"),
    ]


# --- Mantenimiento, incidencias, usuarios y auditoría ---------------------------------------------


def _mantenimientos(report: Report) -> None:
    rows = report.rows
    report.summary = [
        ("Mantenimientos", _fmt(len(rows), 0)),
        ("Por reportes de incidencia", _fmt(sum(1 for v in _values(report, "Reporte de incidencia") if v), 0)),
        ("Con repuestos", _fmt(sum(1 for v in _values(report, "Repuestos") if v), 0)),
        ("Responsables", _fmt(len(set(_values(report, "Responsable"))), 0)),
    ]
    report.charts = [
        _counts("Mantenimientos por tipo", _values(report, "Tipo"), "mantenimientos"),
        _counts("Estado final del componente", _values(report, "Estado final"), "mantenimientos"),
        _counts("Mantenimientos por dispositivo", _values(report, "Dispositivo"), "mantenimientos"),
    ]


def _incidencias(report: Report) -> None:
    hours = [v for v in (_num(x) for x in _values(report, "Horas hasta finalizar")) if v is not None]
    accept = [v for v in (_num(x) for x in _values(report, "Horas hasta aceptar")) if v is not None]
    report.summary = [
        ("Reportes", _fmt(len(report.rows), 0)),
        ("Finalizados", _fmt(len(hours), 0)),
        ("Promedio hasta aceptar", f"{_fmt(sum(accept) / len(accept), 1)} h" if accept else "—"),
        ("Promedio hasta finalizar", f"{_fmt(sum(hours) / len(hours), 1)} h" if hours else "—"),
    ]
    report.charts = [
        _counts(
            "Reportes por estado",
            _values(report, "Estado"),
            "reportes",
            order=["Abierto", "Aceptado", "En progreso", "Finalizado"],
        ),
        _counts("Reportes por prioridad", _values(report, "Prioridad"), "reportes", order=["Alta", "Media", "Baja"]),
    ]


def _usuarios(report: Report) -> None:
    accounts = _values(report, "Cuenta")
    roles = [role for value in _values(report, "Roles") for role in (value or "").split(", ") if role]
    report.summary = [
        ("Usuarios", _fmt(len(accounts), 0)),
        ("Cuentas activas", _fmt(accounts.count("Activa"), 0)),
        ("Perfiles completos", _fmt(_values(report, "Perfil completo").count("Sí"), 0)),
    ]
    report.charts = [
        _counts("Usuarios por rol", roles, "usuarios"),
        _counts("Usuarios por cargo", _values(report, "Cargo"), "usuarios", horizontal=True),
    ]


def _auditoria(report: Report) -> None:
    report.summary = [
        ("Operaciones registradas", _fmt(len(report.rows), 0)),
        ("Usuarios distintos", _fmt(len(set(_values(report, "Usuario"))), 0)),
        ("Tipos de acción", _fmt(len(set(_values(report, "Acción"))), 0)),
    ]
    actions = [str(a).split(".")[0] for a in _values(report, "Acción")]
    report.charts = [
        _by_day("Operaciones por día", report, "Fecha", "operaciones"),
        _counts("Operaciones por módulo", actions, "operaciones", horizontal=True),
    ]


DECORATORS: dict[str, Callable[[Report], None]] = {
    "volumen": _series,
    "variable": _series,
    "mediciones": _mediciones,
    "dispositivos": _dispositivos,
    "inventario_stock": _inventario_stock,
    "inventario_movimientos": _inventario_movimientos,
    "inventario_periodo": _inventario_periodo,
    "inventario_conteo": _inventario_conteo,
    "inventario_kardex": _inventario_kardex,
    "inventario_consumo": _inventario_consumo,
    "mantenimientos": _mantenimientos,
    "incidencias": _incidencias,
    "usuarios": _usuarios,
    "auditoria": _auditoria,
}


def add_charts(kind: str, report: Report) -> Report:
    """Completa el resumen y los gráficos del reporte (si el tipo los define)."""
    decorate = DECORATORS.get(kind)
    if decorate is not None:
        decorate(report)
    return report


def readable(code: object) -> str:
    """Nombre legible de un código guardado (p. ej. «calibracion» → «Calibración»)."""
    return _label(code)
