"""Genera complementos_informe.drawio: diagramas del informe final que no existían.

Páginas: paquetes, cuatro diagramas de colaboración (uno por proceso), conexiones del prototipo,
diagrama de Ishikawa y árbol de problemas. Se basan en el código actual (backend/app, frontend/src,
firmware/) y en la problemática del informe.

Uso:  python3 generar_complementos.py
      drawio -x -f png -s 2 -a -o png/complementos/ complementos_informe.drawio
"""

from itertools import count
from pathlib import Path
from xml.sax.saxutils import escape

_ids = count(2)
FONT = "fontFamily=Arial;fontSize=12;"


def _v(text: str) -> str:
    return escape(text, {chr(34): "&quot;"}).replace("\n", "&lt;br&gt;")


class Page:
    def __init__(self, name: str, width: int = 1600, height: int = 1100) -> None:
        self.name, self.width, self.height, self.cells = name, width, height, []

    def add(self, value: str, x: float, y: float, w: float, h: float, style: str, parent: str = "1") -> str:
        cid = f"c{next(_ids)}"
        self.cells.append(
            f'<mxCell id="{cid}" value="{_v(value)}" style="{style}" vertex="1" parent="{parent}">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
        )
        return cid

    def edge(self, src: str, dst: str, style: str, label: str = "", points: list[tuple[float, float]] | None = None) -> str:
        cid = f"c{next(_ids)}"
        pts = ""
        if points:
            pts = "<Array as=\"points\">" + "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in points) + "</Array>"
        self.cells.append(
            f'<mxCell id="{cid}" value="{_v(label)}" style="{style}" edge="1" parent="1" '
            f'source="{src}" target="{dst}"><mxGeometry relative="1" as="geometry">{pts}</mxGeometry></mxCell>'
        )
        return cid

    def xml(self) -> str:
        return (
            f'<diagram id="{abs(hash(self.name))}" name="{escape(self.name)}"><mxGraphModel dx="0" dy="0" grid="0" '
            f'gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
            f'pageWidth="{self.width}" pageHeight="{self.height}" background="#FFFFFF" math="0" shadow="0"><root>'
            '<mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(self.cells) + "</root></mxGraphModel></diagram>"
        )


PKG = FONT + "shape=folder;tabWidth=110;tabHeight=22;tabPosition=left;html=1;whiteSpace=wrap;verticalAlign=top;align=left;spacingLeft=8;spacingTop=24;fontStyle=1;strokeColor=#333333;"
SUB = FONT + "shape=folder;tabWidth=50;tabHeight=14;tabPosition=left;html=1;whiteSpace=wrap;verticalAlign=middle;align=center;spacingTop=10;strokeColor=#333333;fillColor=#FFFFFF;fontSize=11;"
DEP = FONT + "endArrow=open;endSize=10;dashed=1;html=1;rounded=0;strokeColor=#333333;fontSize=11;labelBackgroundColor=#FFFFFF;"


def paquetes() -> Page:
    p = Page("Paquetes", 1500, 980)
    # Frontend
    fe = p.add("Frontend (React + TypeScript)", 30, 30, 640, 250, PKG + "fillColor=#E8F1FB;")
    f_app = p.add("app\n(rutas y diseño)", 50, 90, 110, 70, SUB)
    f_feat = p.add("features\n(auth, dashboard, devices, fog-collectors, incidents, inventory, maintenance, analysis, ml, firmware…)", 190, 80, 260, 90, SUB)
    f_comp = p.add("components\n(ui, common)", 480, 90, 160, 70, SUB)
    f_lib = p.add("lib\n(cliente Axios)", 190, 195, 140, 65, SUB)
    f_types = p.add("types", 360, 195, 110, 65, SUB)
    # Firmware
    fw = p.add("Firmware de la estación (ESP32 · PlatformIO)", 760, 30, 700, 250, PKG + "fillColor=#FFF4E5;")
    fw_src = p.add("src\n(lectura de sensores, cola LittleFS, envío HTTP/JSON, actualización OTA)", 790, 90, 300, 90, SUB)
    fw_inc = p.add("include\n(config.h: pines y versión)", 1120, 90, 210, 70, SUB)
    fw_lib = p.add("bibliotecas\n(BME280, DHT, ArduinoJson)", 1120, 190, 210, 70, SUB)
    # Backend
    be = p.add("Backend (FastAPI · monolito modular en tres capas)", 30, 340, 1430, 380, PKG + "fillColor=#EEF7EE;")
    pres = p.add("presentation", 60, 400, 330, 290, PKG + "fillColor=#FFFFFF;tabWidth=90;")
    api = p.add("api\n(routers: auth, users, admin, infrastructure, measurements, incidents, inventory, reports, analysis, ml, firmware)", 80, 450, 290, 110, SUB)
    sch = p.add("schemas\n(modelos Pydantic de entrada y salida)", 80, 590, 290, 80, SUB)
    bus = p.add("business", 430, 400, 380, 290, PKG + "fillColor=#FFFFFF;tabWidth=80;")
    svc = p.add("services\n(reglas de cada módulo y auditoría)", 450, 450, 340, 80, SUB)
    rul = p.add("rules\n(mediciones, contraseñas, firmware)", 450, 560, 160, 110, SUB)
    ml = p.add("ml\n(features, inference, servicio de predicción)", 630, 560, 160, 110, SUB)
    dat = p.add("data", 850, 400, 330, 290, PKG + "fillColor=#FFFFFF;tabWidth=60;")
    rep = p.add("repositories\n(acceso con SQLAlchemy)", 870, 450, 290, 80, SUB)
    mod = p.add("models\n(entidades ORM)", 870, 560, 135, 110, SUB)
    db = p.add("database\n(sesión y motor)", 1025, 560, 135, 110, SUB)
    core = p.add("core\n(config, security, permissions, errors, clock)", 1210, 450, 230, 110, SUB)
    # Soporte
    p.add("Recursos y herramientas", 30, 780, 1430, 170, PKG + "fillColor=#F5F5F5;")
    nb = p.add("notebooks\n(preparación y entrenamiento del modelo)", 80, 840, 260, 80, SUB)
    art = p.add("artifacts\n(modelo entrenado .joblib)", 400, 840, 230, 80, SUB)
    alem = p.add("alembic\n(migraciones del esquema)", 690, 840, 230, 80, SUB)
    pg = p.add("PostgreSQL", 980, 840, 180, 80, FONT + "shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=12;whiteSpace=wrap;html=1;fillColor=#FFFFFF;")
    tests = p.add("tests\n(pytest)", 1220, 840, 180, 80, SUB)
    # Dependencias
    p.edge(f_app, f_feat, DEP)
    p.edge(f_feat, f_comp, DEP)
    p.edge(f_feat, f_lib, DEP)
    p.edge(f_feat, f_types, DEP)
    p.edge(f_lib, api, DEP, "«HTTP/JSON»")
    p.edge(fw_src, api, DEP, "«HTTP/JSON»")
    p.edge(fw_src, fw_inc, DEP)
    p.edge(fw_src, fw_lib, DEP)
    p.edge(api, sch, DEP)
    p.edge(api, svc, DEP)
    p.edge(svc, rul, DEP)
    p.edge(svc, ml, DEP)
    p.edge(svc, rep, DEP)
    p.edge(rep, mod, DEP)
    p.edge(rep, db, DEP)
    p.edge(svc, core, DEP, "", [(800, 430), (1325, 430)])
    p.edge(db, pg, DEP, "«SQL»")
    p.edge(ml, art, DEP, "«carga»")
    p.edge(nb, art, DEP, "«genera»")
    p.edge(nb, ml, DEP, "«reutiliza»")
    p.edge(alem, mod, DEP)
    p.edge(tests, svc, DEP, "", [(1310, 760), (620, 760)])
    return p


OBJ = FONT + "rounded=0;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor=#333333;fontStyle=4;"
ACT = FONT + "shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;outlineConnect=0;"
LINK = FONT + "endArrow=none;html=1;rounded=0;strokeColor=#333333;fontSize=11;labelBackgroundColor=#FFFFFF;align=left;"


def colaboracion(name: str, actors: list[tuple[str, float, float]], objects: list[tuple[str, float, float]],
                 links: list[tuple[str, str, str]], width: int = 2250, height: int = 900) -> Page:
    p = Page(name, width, height)
    ids: dict[str, str] = {}
    geo: dict[str, tuple[float, float]] = {}
    for label, x, y in actors:
        ids[label] = p.add(label, x, y, 40, 70, ACT)
        geo[label] = (x + 20, y + 35)
    for label, x, y in objects:
        ids[label] = p.add(label, x, y, 270, 60, OBJ)
        geo[label] = (x + 135, y + 30)
    msg = FONT + "text;html=1;whiteSpace=wrap;align=center;verticalAlign=middle;fontSize=11;fillColor=none;strokeColor=none;"
    for a, b, text in links:
        p.edge(ids[a], ids[b], LINK + "endArrow=open;endSize=8;")
        (x1, y1), (x2, y2) = geo[a], geo[b]
        lines = text.count("\n") + 1
        w, h = (300 if abs(y2 - y1) < 40 else 380), 20 * lines + 8
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        dy = -h / 2 - 16 if abs(y2 - y1) < 40 else 0
        dx = 0 if abs(y2 - y1) < 40 else (w / 2 + 12 if (x2 - x1) * (y2 - y1) >= 0 else -(w / 2 + 12))
        p.add(text, mx - w / 2 + dx, my - h / 2 + dy, w, h, msg)
    return p


def colab_incidencias() -> Page:
    return colaboracion(
        "Colaboración - Incidencias",
        [("Docente", 40, 80), ("Técnico de mantenimiento", 40, 640)],
        [
            (":PantallaReportes", 340, 90), (":PantallaIncidencias", 340, 650), (":incidents (API)", 860, 370),
            (":IncidentService", 1380, 370), (":IncidentRepository", 1900, 60), (":NotificationService", 1900, 370),
            (":MaintenanceService", 1380, 760), (":InventoryService", 1900, 760), (":AuditService", 1900, 570),
        ],
        [
            ("Docente", ":PantallaReportes", "1: reportarIncidencia(estación, descripción, prioridad)"),
            (":PantallaReportes", ":incidents (API)", "1.1: POST /incidents"),
            ("Técnico de mantenimiento", ":PantallaIncidencias", "2: aceptar(reporte)\n3: iniciar(reporte)\n4: finalizar(reporte, repuestos)"),
            (":PantallaIncidencias", ":incidents (API)", "2.1: POST /incidents/{id}/accept\n3.1: POST /incidents/{id}/start\n4.1: POST /incidents/{id}/finish"),
            (":incidents (API)", ":IncidentService", "1.2: report()\n2.2: accept()\n3.2: start()\n4.2: finish()"),
            (":IncidentService", ":IncidentRepository", "1.3: add(reporte)\n2.3, 3.3, 4.3: actualizar estado"),
            (":IncidentService", ":NotificationService", "1.4: notify(mantenimiento, director)\n2.4, 4.6: notify(reportante)"),
            (":IncidentService", ":MaintenanceService", "4.4: consume_parts(registro, repuestos)"),
            (":MaintenanceService", ":InventoryService", "4.4.1 *: apply_movement(salida_mantenimiento)"),
            (":IncidentService", ":AuditService", "1.5, 2.5, 3.4, 4.5: record(acción)"),
        ],
    )


def colab_recuperacion() -> Page:
    return colaboracion(
        "Colaboración - Recuperación de cuenta",
        [("Usuario", 40, 80), ("Administrador", 40, 640)],
        [
            (":PantallaInicioSesión", 340, 90), (":PantallaRecuperaciones", 340, 650), (":auth (API)", 860, 90),
            (":admin (API)", 860, 650), (":RecoveryService", 1380, 420), (":AuthService", 1380, 90),
            (":RecoveryRequestRepository", 1900, 420), (":UserRepository", 1900, 230), (":SessionRepository", 1900, 610),
            (":AuditService", 1380, 760),
        ],
        [
            ("Usuario", ":PantallaInicioSesión", "1: solicitarRecuperación(usuario)\n3: cambiarContraseñaTemporal()"),
            (":PantallaInicioSesión", ":auth (API)", "1.1: POST /auth/recovery-requests\n3.1: POST /auth/change-password"),
            (":auth (API)", ":RecoveryService", "1.2: submit(usuario, mensaje)"),
            (":auth (API)", ":AuthService", "3.2: change_password()"),
            (":RecoveryService", ":RecoveryRequestRepository", "1.3: add(solicitud «pendiente»)\n2.3: actualizar(«aprobada»/«rechazada»)"),
            ("Administrador", ":PantallaRecuperaciones", "2: aprobar(solicitud) / rechazar(solicitud)"),
            (":PantallaRecuperaciones", ":admin (API)", "2.1: POST /admin/recovery-requests/{id}/approve"),
            (":admin (API)", ":RecoveryService", "2.2: approve(id) / reject(id)"),
            (":RecoveryService", ":UserRepository", "2.4: contraseña temporal y cambio obligatorio"),
            (":RecoveryService", ":SessionRepository", "2.5: revocar sesiones activas"),
            (":RecoveryService", ":AuditService", "1.4, 2.6: record(acción)"),
            (":AuthService", ":UserRepository", "3.3: guardar nuevo hash scrypt"),
        ],
    )


def colab_mantenimiento() -> Page:
    return colaboracion(
        "Colaboración - Mantenimiento con repuestos",
        [("Técnico de mantenimiento", 40, 330)],
        [
            (":PantallaMantenimiento", 340, 340), (":maintenance (API)", 860, 340), (":MaintenanceService", 1380, 340),
            (":MaintenanceRepository", 1900, 60), (":InventoryService", 1380, 680), (":InventoryItemRepository", 1900, 560),
            (":InventoryMovementRepository", 1900, 800), (":AuditService", 1900, 340),
        ],
        [
            ("Técnico de mantenimiento", ":PantallaMantenimiento", "1: registrarMantenimiento(dispositivo, tipo, repuestos)"),
            (":PantallaMantenimiento", ":maintenance (API)", "1.1: POST /maintenance"),
            (":maintenance (API)", ":MaintenanceService", "1.2: register(datos, repuestos)"),
            (":MaintenanceService", ":MaintenanceRepository", "1.3: validate_target() · add(registro)"),
            (":MaintenanceService", ":InventoryService", "1.4 *: apply_movement(repuesto, cantidad)"),
            (":InventoryService", ":InventoryItemRepository", "1.4.1: get_for_update(repuesto)\n1.4.2: actualizar stock"),
            (":InventoryService", ":InventoryMovementRepository", "1.4.3: add(movimiento)"),
            (":MaintenanceService", ":AuditService", "1.5: record(«mantenimiento.registrar»)"),
        ],
    )


def colab_inventario() -> Page:
    return colaboracion(
        "Colaboración - Periodo de inventario",
        [("Administrador", 40, 330)],
        [
            (":PantallaPeriodos", 340, 340), (":inventory (API)", 860, 340), (":InventoryPeriodService", 1380, 340),
            (":InventoryPeriodRepository", 1900, 60), (":InventoryService", 1380, 700), (":ReportService", 860, 760),
            (":InventoryMovementRepository", 1900, 700), (":AuditService", 1900, 380),
        ],
        [
            ("Administrador", ":PantallaPeriodos", "1: abrirPeriodo()\n2: registrarConteo()\n3: cerrarPeriodo()\n4: exportarActa()"),
            (":PantallaPeriodos", ":inventory (API)", "1.1: POST /inventory/periods\n2.1: PUT /inventory/periods/{id}/counts\n3.1: POST /inventory/periods/{id}/close"),
            (":inventory (API)", ":InventoryPeriodService", "1.2: create()\n2.2: register_counts()\n3.2: close()"),
            (":InventoryPeriodService", ":InventoryPeriodRepository", "1.3: add(periodo)\n2.3: guardar conteos\n3.4: congelar saldos"),
            (":InventoryPeriodService", ":InventoryService", "3.3 *: apply_movement(ajuste_sobrante / ajuste_faltante)"),
            (":InventoryService", ":InventoryMovementRepository", "3.3.1: add(movimiento)"),
            (":InventoryPeriodService", ":AuditService", "1.4, 2.4, 3.5: record(acción)"),
            (":PantallaPeriodos", ":ReportService", "4.1: GET reporte del periodo (PDF/Excel)"),
        ],
    )


def prototipo() -> Page:
    p = Page("Prototipo - Conexiones", 1700, 820)
    box = FONT + "rounded=1;whiteSpace=wrap;html=1;strokeColor=#333333;arcSize=6;"
    esp = p.add("ESP32 DevKit V1\n(ESP32-WROOM-32 · Wi-Fi 2,4 GHz · lógica de 3,3 V)\n\n3V3 · GND · GPIO 25 · GPIO 26 · GPIO 27 · GPIO 32", 760, 280, 330, 190, box + "fillColor=#E8F1FB;fontStyle=1;")
    bme = p.add("BME280\ntemperatura · humedad · presión\n(I²C, dirección 0x76)", 60, 90, 280, 100, box + "fillColor=#EEF7EE;")
    dht = p.add("DHT11\ntemperatura · humedad\n(respaldo del BME280)", 60, 330, 280, 100, box + "fillColor=#EEF7EE;")
    rain = p.add("Pluviómetro de balancín\nvolumen de agua captada\n(interruptor reed)", 60, 570, 280, 100, box + "fillColor=#EEF7EE;")
    usb = p.add("Alimentación USB 5 V", 1300, 600, 230, 70, box + "fillColor=#FFF4E5;")
    srv = p.add("Servidor local de la institución\nAPI FastAPI · PostgreSQL", 1300, 60, 280, 90, box + "fillColor=#F5F5F5;")
    ap = p.add("Punto de acceso Wi-Fi\n(red local)", 1330, 340, 220, 70, box + "fillColor=#F5F5F5;")
    wire = FONT + "endArrow=none;html=1;rounded=0;strokeColor=#1F4E79;strokeWidth=2;fontSize=11;labelBackgroundColor=#FFFFFF;"
    p.edge(bme, esp, wire, "SDA → GPIO 27 · SCL → GPIO 26\nVCC → 3V3 · GND → GND · SDO → GND")
    p.edge(dht, esp, wire, "DATA → GPIO 25 (10 kΩ a 3V3)\nVCC → 3V3 · GND → GND")
    p.edge(rain, esp, wire, "terminal 1 → GPIO 32 (pull-up interno)\nterminal 2 → GND")
    p.edge(usb, esp, wire, "USB (5 V)")
    net = FONT + "endArrow=classic;html=1;dashed=1;rounded=0;strokeColor=#333333;fontSize=11;labelBackgroundColor=#FFFFFF;"
    p.edge(esp, ap, net, "Wi-Fi")
    p.edge(ap, srv, net, "HTTP/JSON\nPOST /api/v1/iot/measurements/batch")
    return p


def ishikawa() -> Page:
    p = Page("Ishikawa", 1700, 900)
    effect = p.add("Información insuficiente para conocer y planificar el aprovechamiento del agua captada por los atrapanieblas en el riego de los invernaderos del C.E.A. «Ildefonso de las Muñecas»",
                   1340, 350, 330, 170, FONT + "rounded=0;whiteSpace=wrap;html=1;fillColor=#FDE9E7;strokeColor=#B03A2E;fontStyle=1;")
    spine_start = p.add("", 60, 433, 1, 1, "shape=waypoint;fillColor=none;strokeColor=none;")
    p.edge(spine_start, effect, "endArrow=block;endFill=1;html=1;strokeWidth=3;strokeColor=#333333;")
    cats = {
        "MEDIO AMBIENTE": ["Niebla, humedad y viento variables", "Estaciones seca y húmeda marcadas", "Dependencia de un único ojo de agua"],
        "MÉTODOS": ["Riego planificado por experiencia", "Sin procedimiento de registro", "Sin estimación del volumen captado"],
        "MEDICIÓN": ["No se mide el volumen captado", "Sin registro de variables meteorológicas", "Sin histórico para comparar"],
        "MAQUINARIA Y TECNOLOGÍA": ["Sin estación de monitoreo", "Sin sistema de información", "Internet limitado en la zona"],
        "MANO DE OBRA": ["Personal sin herramientas de análisis", "Mantenimientos sin registro", "Responsables con varias funciones"],
        "MATERIALES": ["Repuestos sin control de stock", "Malla y estructura sin seguimiento", "Sensores sin calibración registrada"],
    }
    head = FONT + "rounded=0;whiteSpace=wrap;html=1;fillColor=#1F4E79;fontColor=#FFFFFF;fontStyle=1;strokeColor=none;"
    cause = FONT + "text;html=1;whiteSpace=wrap;align=left;verticalAlign=middle;fontSize=11;"
    bone = "endArrow=none;html=1;strokeWidth=2;strokeColor=#333333;"
    for k, (name, items) in enumerate(cats.items()):
        col, top = k % 3, k < 3
        x = 130 + col * 400
        hy = 40 if top else 750
        h = p.add(name, x, hy, 230, 40, head)
        anchor = p.add("", x + 290, 433, 1, 1, "shape=waypoint;fillColor=none;strokeColor=none;")
        p.edge(h, anchor, bone)
        for j, item in enumerate(items):
            y = (120 + j * 100) if top else (700 - j * 100)
            hx, hy0 = x + 115, (hy + 40 if top else hy)
            bx = hx + (x + 290 - hx) * abs((y + 20) - hy0) / abs(433 - hy0)
            p.add("• " + item, bx - 278, y, 270, 40, cause.replace("align=left", "align=right"))
    return p


def arbol() -> Page:
    p = Page("Árbol de problemas", 1500, 1000)
    eff = FONT + "rounded=1;whiteSpace=wrap;html=1;fillColor=#EEF7EE;strokeColor=#2E7D32;arcSize=8;"
    cau = FONT + "rounded=1;whiteSpace=wrap;html=1;fillColor=#E8F1FB;strokeColor=#1F4E79;arcSize=8;"
    core = FONT + "rounded=0;whiteSpace=wrap;html=1;fillColor=#FDE9E7;strokeColor=#B03A2E;fontStyle=1;fontSize=13;"
    up = "endArrow=block;endFill=1;html=1;strokeColor=#333333;"
    p.add("EFECTOS", 40, 40, 160, 30, FONT + "text;fontStyle=1;")
    p.add("CAUSAS", 40, 880, 160, 30, FONT + "text;fontStyle=1;")
    problem = p.add("Información insuficiente sobre el agua captada mediante atrapanieblas para planificar el riego de los invernaderos del C.E.A. «Ildefonso de las Muñecas»",
                    360, 450, 780, 90, core)
    effects_hi = [
        "Prácticas agrícolas formativas reprogramadas, reducidas o suspendidas",
        "Inversiones en captación decididas sin evidencia del aporte real",
        "Menor continuidad de la formación técnica productiva",
    ]
    effects_lo = [
        "Riego planificado sin conocer el agua disponible",
        "No se puede evaluar si el atrapanieblas cubre parte de la demanda",
        "Fallas del equipo detectadas tarde y repuestos sin control",
    ]
    causes_hi = [
        "Ausencia de registro continuo de variables meteorológicas",
        "No se mide el volumen captado por el atrapanieblas",
        "Mantenimiento e inventario de repuestos sin trazabilidad",
    ]
    causes_lo = [
        "Dependencia de un único ojo de agua comunitario de caudal variable",
        "Condiciones de niebla, humedad y viento cambiantes durante el año",
        "Falta de una herramienta que estime el volumen a partir de los datos",
    ]
    lo_e = [p.add(t, 180 + i * 400, 300, 340, 70, eff) for i, t in enumerate(effects_lo)]
    hi_e = [p.add(t, 180 + i * 400, 110, 340, 70, eff) for i, t in enumerate(effects_hi)]
    hi_c = [p.add(t, 180 + i * 400, 620, 340, 70, cau) for i, t in enumerate(causes_hi)]
    lo_c = [p.add(t, 180 + i * 400, 800, 340, 70, cau) for i, t in enumerate(causes_lo)]
    for e in lo_e:
        p.edge(problem, e, up)
    for a, b in zip(lo_e, hi_e, strict=True):
        p.edge(a, b, up)
    for c in hi_c:
        p.edge(c, problem, up)
    for a, b in zip(lo_c, hi_c, strict=True):
        p.edge(a, b, up)
    return p


import re as _re


def bigger(page: Page, factor: float) -> Page:
    """Agranda la letra para que el diagrama siga legible al reducirse al ancho de la página."""
    page.cells = [_re.sub(r"fontSize=(\d+)", lambda m: f"fontSize={round(int(m.group(1)) * factor)}", c) for c in page.cells]
    page.cells = [c if "fontSize=" in c else c.replace('style="', 'style="fontSize=%d;' % round(12 * factor), 1) for c in page.cells]
    return page


pages = [bigger(paquetes(), 1.3), bigger(colab_incidencias(), 1.35), bigger(colab_recuperacion(), 1.35),
         bigger(colab_mantenimiento(), 1.35), bigger(colab_inventario(), 1.35), bigger(prototipo(), 1.4),
         bigger(ishikawa(), 1.35), bigger(arbol(), 1.3)]
out = Path(__file__).with_name("complementos_informe.drawio")
out.write_text('<mxfile host="generar_complementos.py">' + "".join(p.xml() for p in pages) + "</mxfile>", encoding="utf-8")
print(out, len(pages), "páginas")
