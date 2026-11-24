"""Genera los diagramas de clases (alto y bajo nivel) y el diagrama físico a partir del código.

Los diagramas se construyen leyendo los modelos SQLAlchemy y los servicios del backend, de modo que
siempre coinciden con el sistema implementado. Se dibujan con Graphviz (dot) y se exportan a PNG a
300 ppp, divididos por módulo para que sean legibles en una página del informe.

Uso (desde la raíz del repositorio):
    backend/.venv/bin/python docs/diagramas/generar_diagramas_datos.py
Salida: docs/diagramas/dot/*.dot y docs/diagramas/png/datos/*.png
"""

import html
import inspect
import subprocess
import sys
import typing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import inspect as sa_inspect  # noqa: E402
from sqlalchemy.dialects import postgresql  # noqa: E402

import app.data.models  # noqa: E402,F401  (registra todos los modelos)
from app.data.database import Base  # noqa: E402

OUT_DOT = ROOT / "docs" / "diagramas" / "dot"
OUT_PNG = ROOT / "docs" / "diagramas" / "png" / "datos"

# Paleta del sistema (DESIGN.md): verde bosque, salvia clara, arena y crema.
INK = "#2B4D3B"
HEAD = "#B9D2C2"
SAND = "#E7D7C7"
CREAM = "#FBF7F1"
MUTED = "#55675C"
FONT = "DejaVu Sans"
MONO = "DejaVu Sans Mono"

# Grupos de tablas: cada uno es una figura que cabe en una página horizontal del informe.
MODULES: dict[str, tuple[str, list[str]]] = {
    "acceso": ("Seguridad: acceso, sesiones y auditoría",
               ["users", "user_roles", "roles", "role_permissions", "permissions", "user_sessions", "audit_logs",
                "account_recovery_requests"]),
    "personas": ("Seguridad: datos personales y formación",
                 ["user_profiles", "user_degrees", "positions", "academic_levels", "institutions"]),
    "infraestructura": ("Infraestructura física", ["locations", "fog_collectors", "tanks", "greenhouses"]),
    "dispositivos": ("Dispositivos IoT y firmware",
                     ["devices", "device_credentials", "device_locations", "firmware_releases"]),
    "mediciones": ("Sensores y mediciones",
                   ["sensors", "sensor_types", "measurement_batches", "sensor_readings", "sensor_calibrations"]),
    "inventario": ("Inventario de repuestos",
                   ["inventory_categories", "inventory_items", "inventory_item_compatibility",
                    "inventory_movement_types", "inventory_movements"]),
    "periodos": ("Periodos de inventario", ["inventory_periods", "inventory_counts", "inventory_period_balances"]),
    "mantenimiento": ("Mantenimiento", ["maintenance_records", "maintenance_items"]),
    "procesos": ("Incidencias, reubicaciones y notificaciones",
                 ["incident_reports", "fog_collector_relocations", "notifications"]),
}

# El diagrama físico muestra todas las columnas: los grupos más anchos se parten en dos figuras.
PHYSICAL_SPLIT: dict[str, list[tuple[str, str, list[str]]]] = {
    "acceso": [
        ("usuarios", "Usuarios, roles y permisos", ["users", "user_roles", "roles", "role_permissions", "permissions"]),
        ("sesiones", "Sesiones, auditoría y recuperación de cuenta",
         ["user_sessions", "audit_logs", "account_recovery_requests", "users"]),
    ],
    "procesos": [
        ("incidencias", "Incidencias y notificaciones", ["incident_reports", "notifications"]),
        ("reubicaciones", "Reubicaciones de atrapanieblas", ["fog_collector_relocations"]),
    ],
}

# Servicios (lógica de negocio) de cada módulo para el diagrama de clases de bajo nivel.
SERVICES: dict[str, tuple[str, list[str]]] = {
    "servicios_seguridad": ("Lógica de negocio: seguridad", [
        "auth_service:AuthService", "user_service:UserService", "user_service:RoleService",
        "recovery_service:RecoveryService", "audit_service:AuditService",
    ]),
    "servicios_iot": ("Lógica de negocio: IoT y mediciones", [
        "device_service:DeviceService",
        "device_service:SensorService", "device_service:DeviceAuthService", "ingestion_service:IngestionService",
        "measurement_service:MeasurementService", "firmware_service:FirmwareService",
    ]),
    "servicios_inventario": ("Lógica de negocio: inventario y mantenimiento", [
        "inventory_service:InventoryService", "inventory_period_service:InventoryPeriodService",
        "maintenance_service:MaintenanceService",
    ]),
    "servicios_procesos": ("Lógica de negocio: procesos", [
        "incident_service:IncidentService",
        "relocation_service:RelocationService", "notification_service:NotificationService",
        "auto_incident_service:AutoIncidentService",
    ]),
}

PG = postgresql.dialect()
MAPPERS = {m.class_.__tablename__: m for m in Base.registry.mappers}
TABLES = Base.metadata.tables


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def pg_type(column) -> str:  # noqa: ANN001
    text = column.type.compile(dialect=PG).lower()
    return (
        text.replace("timestamp with time zone", "timestamptz")
        .replace("timestamp without time zone", "timestamp")
        .replace("character varying", "varchar")
        .replace("double precision", "float8")
    )


def py_type(column) -> str:  # noqa: ANN001
    type_name = column.type.__class__.__name__.lower()
    if type_name in ("inet", "cidr"):
        return "inet"
    if "json" in type_name:
        return "json"
    try:
        name = column.type.python_type.__name__
    except NotImplementedError:
        name = "json"
    return {"Decimal": "decimal", "datetime": "datetime", "date": "date", "UUID": "uuid", "dict": "json"}.get(name, name)


PAGE_W_CM, PAGE_H_CM = 22.9, 14.0  # área útil de una página horizontal carta (márgenes 2,5 cm y pie de figura)


def _scale(png: Path) -> float:
    import struct
    w, h = struct.unpack(">II", png.read_bytes()[16:24])
    return min(1.0, PAGE_W_CM / (w / 300 * 2.54), PAGE_H_CM / (h / 300 * 2.54))


def render(name: str, dot: str) -> Path:
    """Exporta a PNG probando las dos direcciones del grafo y conserva la que mejor llena la página."""
    OUT_DOT.mkdir(parents=True, exist_ok=True)
    OUT_PNG.mkdir(parents=True, exist_ok=True)
    png = OUT_PNG / f"{name}.png"
    best: tuple[float, str] | None = None
    for rankdir in ("LR", "TB"):
        variant = dot.replace("rankdir=LR", f"rankdir={rankdir}").replace("rankdir=TB", f"rankdir={rankdir}")
        src = OUT_DOT / f"{name}.dot"
        src.write_text(variant, encoding="utf-8")
        subprocess.run(["dot", "-Tpng", "-Gdpi=300", str(src), "-o", str(png)], check=True)
        scale = _scale(png)
        if best is None or scale > best[0]:
            best = (scale, variant)
    src.write_text(best[1], encoding="utf-8")
    subprocess.run(["dot", "-Tpng", "-Gdpi=300", str(src), "-o", str(png)], check=True)
    return png


def graph_header(title: str, rankdir: str = "LR") -> list[str]:
    # Sin título dentro de la imagen: el informe lo pone en el pie de figura (APA).
    del title
    return [
        "digraph G {",
        f'  graph [rankdir={rankdir}, bgcolor="white", pad=0.3, nodesep=0.35, ranksep=0.7, splines=true, '
        f'fontname="{FONT}"];',
        f'  node [shape=plain, fontname="{FONT}", fontsize=12, color="{INK}"];',
        f'  edge [color="{MUTED}", fontname="{FONT}", fontsize=11, fontcolor="{INK}", arrowsize=0.8];',
    ]


# --- Diagrama físico -------------------------------------------------------------------


def physical_table(table, *, compact: bool = False) -> str:  # noqa: ANN001
    fk_cols = {c.name for c in table.columns if c.foreign_keys}
    uniques = {
        col.name
        for cons in table.constraints
        if cons.__class__.__name__ == "UniqueConstraint" and len(cons.columns) == 1
        for col in cons.columns
    } | {c.name for c in table.columns if c.unique}
    rows = [
        f'<tr><td colspan="3" bgcolor="{INK if not compact else SAND}" align="left">'
        f'<font color="{"white" if not compact else INK}"><b> {esc(table.name)} </b></font></td></tr>'
    ]
    if compact:
        rows.append(f'<tr><td colspan="3" port="id" align="left"><font point-size="9" color="{MUTED}">'
                    f"(tabla de otro módulo)</font></td></tr>")
    else:
        for c in table.columns:
            key = "PK" if c.primary_key else ("FK" if c.name in fk_cols else "")
            flags = " ".join(f for f in ("NN" if not c.nullable and not c.primary_key else "",
                                         "UQ" if c.name in uniques else "") if f)
            name = f"<b>{esc(c.name)}</b>" if c.primary_key else esc(c.name)
            rows.append(
                f'<tr><td align="left"><font color="{MUTED}">{key or " "}</font></td>'
                f'<td align="left">{name}</td>'
                f'<td port="{esc(c.name)}" align="left"><font face="{MONO}" point-size="11" color="{MUTED}">{esc(pg_type(c))}'
                f'{" " + flags if flags else ""}</font></td></tr>'
            )
    return (
        f'<<table border="1" cellborder="0" cellspacing="0" cellpadding="3" color="{INK}" bgcolor="white">'
        + "".join(rows)
        + "</table>>"
    )


def physical_diagram(key: str, title: str | None = None, names: list[str] | None = None) -> Path:
    if names is None:
        title, names = MODULES[key]
    lines = graph_header(title)
    lines.append("  graph [nodesep=0.2, ranksep=0.55];")
    external: set[str] = set()
    edges: list[str] = []
    for name in names:
        for c in TABLES[name].columns:
            for fk in c.foreign_keys:
                target = fk.column.table.name
                if target not in names:
                    external.add(target)
                # De la columna FK (lado derecho) a la tabla referenciada (lado izquierdo): sin bucles.
                edges.append(f'  "{name}":"{c.name}":e -> "{target}":w [arrowhead=none, arrowtail=crow, dir=both];')
    for name in names:
        lines.append(f'  "{name}" [label={physical_table(TABLES[name])}];')
    for name in sorted(external):
        lines.append(f'  "{name}" [label={physical_table(TABLES[name], compact=True)}];')
    lines += edges + ["}"]
    return render(f"fisico_{key}", "\n".join(lines))


# --- Diagrama de clases de bajo nivel --------------------------------------------------------


def entity_methods(cls: type) -> list[str]:
    out = []
    for attr, value in cls.__dict__.items():
        if attr.startswith("_"):
            continue
        if isinstance(value, property):
            ret = typing.get_type_hints(value.fget).get("return") if value.fget else None
            out.append(f"{attr}(): {getattr(ret, '__name__', str(ret).replace('typing.', ''))}")
        elif inspect.isfunction(value):
            out.append(f"{attr}()")
    return out


def class_box(mapper) -> str:  # noqa: ANN001
    cls = mapper.class_
    attrs = []
    for c in mapper.columns:
        mark = "{PK}" if c.primary_key else ("{FK}" if c.foreign_keys else "")
        opt = " [0..1]" if c.nullable and not c.primary_key else ""
        attrs.append(f"{'+'} {c.key}: {py_type(c)}{opt} {mark}".rstrip())
    methods = entity_methods(cls)
    rows = [f'<tr><td bgcolor="{HEAD}"><b>{esc(cls.__name__)}</b></td></tr>',
            '<tr><td align="left" balign="left">' + "<br/>".join(esc(a) for a in attrs) + "</td></tr>",
            '<tr><td align="left" balign="left">' + ("<br/>".join(esc("+ " + m) for m in methods) or " ") + "</td></tr>"]
    return (f'<<table border="1" cellborder="1" cellspacing="0" cellpadding="4" color="{INK}" bgcolor="white">'
            + "".join(rows) + "</table>>")


def service_box(path: str) -> tuple[str, str]:
    module, name = path.split(":")
    cls = getattr(__import__(f"app.business.services.{module}", fromlist=[name]), name)
    methods = []
    for attr, fn in cls.__dict__.items():
        if attr.startswith("_") or not inspect.isfunction(fn):
            continue
        params = [p for p in inspect.signature(fn).parameters if p not in ("self", "ctx")]
        shown = ", ".join(params[:3]) + (", …" if len(params) > 3 else "")
        methods.append(f"+ {attr}({shown})")
    label = (f'<<table border="1" cellborder="1" cellspacing="0" cellpadding="4" color="{INK}" bgcolor="{CREAM}">'
             f'<tr><td bgcolor="{SAND}"><font point-size="9">«servicio»</font><br/><b>{esc(name)}</b></td></tr>'
             '<tr><td align="left" balign="left">' + "<br/>".join(esc(m) for m in methods) + "</td></tr></table>>")
    return name, label


ASSOCIATION_TABLES = {"user_roles", "role_permissions"}  # tablas puras de muchos a muchos


def relations(names: list[str], *, internal_only: bool) -> list[tuple[str, str, str, str, str]]:
    """Asociaciones según las claves foráneas reales (origen, destino, mult. origen, mult. destino, rol)."""
    out = []
    pool = set(names)
    for name in names:
        table = TABLES[name]
        fks = [(c, fk) for c in table.columns for fk in c.foreign_keys]
        if name in ASSOCIATION_TABLES:
            a, b = (fk.column.table.name for _, fk in fks)
            if not internal_only or {a, b} <= pool:
                out.append((a, b, "*", "*", ""))
            continue
        if name not in MAPPERS:
            continue
        for col, fk in fks:
            target = fk.column.table.name
            if internal_only and target not in pool:
                continue
            unique = col.primary_key or col.unique or any(
                cons.__class__.__name__ == "UniqueConstraint" and list(cons.columns) == [col]
                for cons in table.constraints
            )
            m_src = "0..1" if unique else "*"
            m_dst = "1" if not col.nullable else "0..1"
            role = col.name.removesuffix("_id")
            out.append((name, target, m_src, m_dst, "" if role == target.rstrip("s") else role))
    return out


def low_level_diagram(key: str) -> Path:
    title, names = MODULES[key]
    lines = graph_header(title, rankdir="LR")
    lines.append("  graph [nodesep=0.2, ranksep=0.55];")
    mapped = [n for n in names if n in MAPPERS]
    external: set[str] = set()
    for name in mapped:
        lines.append(f'  "{name}" [label={class_box(MAPPERS[name])}];')
    for src, dst, m_src, m_dst, label in relations(names, internal_only=False):
        if src not in mapped:
            external.add(src)
        if dst not in mapped:
            external.add(dst)
        lines.append(f'  "{src}" -> "{dst}" [arrowhead=none, taillabel="{m_src}", headlabel="{m_dst}", '
                     f'label="{esc(label)}", labelfontsize=11];')
    for name in sorted(external):
        lines.append(f'  "{name}" [label=<<table border="1" cellborder="0" cellpadding="4" color="{INK}" '
                     f'bgcolor="{CREAM}"><tr><td><b>{esc(MAPPERS[name].class_.__name__)}</b><br/>'
                     f'<font point-size="8" color="{MUTED}">(otro módulo)</font></td></tr></table>>];')
    lines.append("}")
    return render(f"clases_bajo_{key}", "\n".join(lines))


def services_diagram(key: str) -> Path:
    title, paths = SERVICES[key]
    lines = graph_header(title, rankdir="LR")
    lines.append("  graph [nodesep=0.25, ranksep=0.4];")
    names = []
    for path in paths:
        name, label = service_box(path)
        names.append(name)
        lines.append(f'  "{name}" [label={label}];')
    # Cuadrícula de tres columnas (sin relaciones: cada servicio usa sus repositorios y entidades).
    cols = 3
    for i in range(0, len(names), cols):
        row = names[i:i + cols]
        lines.append("  { rank=same; " + " ".join(f'"{n}";' for n in row) + " }")
    for c in range(cols):
        column = names[c::cols]
        for a, b in zip(column, column[1:]):
            lines.append(f'  "{a}" -> "{b}" [style=invis];')
    lines.append("}")
    return render(f"clases_bajo_{key}", "\n".join(lines))


# --- Diagrama de clases de alto nivel ----------------------------------------------------------

# Clases de dominio principales por área (sin catálogos auxiliares ni tablas de asociación).
HIGH_LEVEL: dict[str, tuple[str, list[str]]] = {
    "seguridad": ("Seguridad y usuarios", ["users", "roles", "permissions", "user_profiles", "user_sessions",
                                           "audit_logs", "account_recovery_requests"]),
    "iot": ("Infraestructura e IoT", ["locations", "fog_collectors", "tanks", "devices", "sensors", "sensor_types",
                                      "sensor_readings", "measurement_batches", "firmware_releases"]),
    "inventario": ("Inventario y mantenimiento", ["inventory_items", "inventory_categories", "inventory_movements",
                                                  "inventory_periods", "maintenance_records"]),
    "procesos": ("Procesos", ["incident_reports", "fog_collector_relocations", "notifications"]),
}


def high_level_diagram() -> Path:
    lines = graph_header("Clases de alto nivel", rankdir="LR")
    lines.append("  graph [nodesep=0.4, ranksep=0.9, newrank=true];")
    lines.append('  node [fontsize=22];')
    included = [n for _, names in HIGH_LEVEL.values() for n in names] + sorted(ASSOCIATION_TABLES)
    for key, (title, names) in HIGH_LEVEL.items():
        lines.append(f'  subgraph "cluster_{key}" {{ label=<<b>{esc(title)}</b>>; labeljust=l; '
                     f'style="rounded,filled"; fillcolor="{CREAM}"; color="{SAND}"; fontsize=22; fontcolor="{INK}";')
        for name in names:
            cls = MAPPERS[name].class_.__name__
            lines.append(f'    "{name}" [label=<<table border="1" cellborder="0" cellpadding="5" color="{INK}" '
                         f'bgcolor="white"><tr><td bgcolor="{HEAD}"><b>{esc(cls)}</b></td></tr></table>>];')
        lines.append("  }")
    security = set(HIGH_LEVEL["seguridad"][1])
    drawn: set[frozenset[str]] = set()
    for src, dst, m_src, m_dst, _ in relations(included, internal_only=True):
        # La trazabilidad (quién registró cada operación) se ve en los diagramas de bajo nivel.
        if dst == "users" and src not in security:
            continue
        if src not in MAPPERS or dst not in MAPPERS:
            continue
        pair = frozenset((src, dst))
        if pair in drawn:
            continue
        drawn.add(pair)
        lines.append(f'  "{src}" -> "{dst}" [arrowhead=none, taillabel="{m_src}", headlabel="{m_dst}", '
                     f'labelfontsize=17, labeldistance=1.8, labelangle=25];')
    lines.append("}")
    return render("clases_alto_nivel", "\n".join(lines))


def legibility(png: Path, base_pt: float = 10) -> str:
    """Tamaño efectivo de la letra al insertar la figura en una página horizontal del informe."""
    import struct
    w, h = struct.unpack(">II", png.read_bytes()[16:24])
    scale = _scale(png)
    return f"{png.name}: {w / 300 * 2.54:.0f}×{h / 300 * 2.54:.0f} cm, escala {scale:.2f}, letra ≈ {base_pt * scale:.1f} pt"


if __name__ == "__main__":
    produced = [(high_level_diagram(), 22)]
    for module in MODULES:
        produced.append((low_level_diagram(module), 12))
        if module in PHYSICAL_SPLIT:
            for sub, title, names in PHYSICAL_SPLIT[module]:
                produced.append((physical_diagram(f"{module}_{sub}", title, names), 12))
        else:
            produced.append((physical_diagram(module), 12))
    for key in SERVICES:
        produced.append((services_diagram(key), 12))
    for path, pt in produced:
        print(legibility(path, pt))
