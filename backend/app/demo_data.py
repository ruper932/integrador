"""Datos de demostración para desarrollo y capacitación.

Carga usuarios de cada rol (excepto administrador), infraestructura, estaciones IoT con 30 días
de lecturas SIMULADAS, inventario con periodos cerrados y abiertos, mantenimientos, reportes de
incidencia en cada etapa de atención y solicitudes de recuperación. Todo pasa por los servicios
del sistema, de modo que se aplican las mismas validaciones y queda registro en la auditoría.

Importante: las lecturas son simuladas. Una base con estos datos no debe usarse para entrenar
el modelo de predicción.

Uso: python -m app.cli seed-demo
"""

import math
import random
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.business.services.context import RequestContext
from app.business.services.device_service import DeviceService, SensorService
from app.business.services.incident_service import IncidentService
from app.business.services.infrastructure_service import (
    fog_collector_service,
    greenhouse_service,
    location_service,
    tank_service,
)
from app.business.services.ingestion_service import IncomingReading, IngestionService
from app.business.services.inventory_period_service import InventoryPeriodService
from app.business.services.inventory_service import InventoryService
from app.business.services.maintenance_service import MaintenanceService, UsedPart
from app.business.services.recovery_service import RecoveryService
from app.business.services.user_service import UserService
from app.core.clock import utcnow
from app.core.permissions import ROLE_ADMIN
from app.data.models.iot import SensorCalibration
from app.data.models.security import User
from app.data.repositories.iot import DeviceRepository, SensorCalibrationRepository, SensorTypeRepository
from app.data.repositories.people import AcademicLevelRepository, InstitutionRepository, PositionRepository
from app.data.repositories.security import RoleRepository, UserRepository

DEMO_PASSWORD = "Atina-Demo-2026"  # noqa: S105 - solo para cuentas de demostración
MARKER_DEVICE = "esp32-01"
READING_DAYS = 30
SEED = 2026


class SeedError(Exception):
    pass


@dataclass(frozen=True)
class DemoUser:
    username: str
    role: str
    position: str
    first_names: str
    paternal: str
    maternal: str | None
    ci: str
    issued: str
    phone: str
    institutional_email: str | None
    personal_email: str | None
    address: str
    degrees: tuple[tuple[str, str, str, int], ...]  # (nivel, título, sigla institución, año)


USERS = [
    DemoUser(
        "rmamani",
        "director",
        "director",
        "Rosa Elena",
        "Mamani",
        "Quispe",
        "4876512",
        "LP",
        "71234561",
        "rmamani@cea-ildefonso.edu.bo",
        "rosa.mamani@example.com",
        "Comunidad Titicachi, Chuma",
        (
            ("maestro_normalista", "Maestra en Educación Primaria Comunitaria Vocacional", "ESFM Warisata", 2004),
            ("licenciatura", "Licenciatura en Ciencias de la Educación", "UMSA", 2011),
        ),
    ),
    DemoUser(
        "jchoque",
        "docente",
        "docente",
        "Juan Carlos",
        "Choque",
        "Apaza",
        "6123478",
        "LP",
        "73456782",
        "jchoque@cea-ildefonso.edu.bo",
        None,
        "Zona central, Chuma",
        (("tecnico_superior", "Técnico Superior en Agropecuaria", "UPEA", 2014),),
    ),
    DemoUser(
        "lticona",
        "docente",
        "docente",
        "Lucía",
        "Ticona",
        None,
        "7345612",
        "LP",
        "67891234",
        None,
        "lucia.ticona@example.com",
        "Comunidad Titicachi",
        (("bachiller", "Bachiller en Humanidades Técnico Humanístico", "EIS PDM", 2019),),
    ),
    DemoUser(
        "pcondori",
        "director",
        "administrativo",
        "Pedro",
        "Condori",
        "Limachi",
        "5678123",
        "LP",
        "76543219",
        "pcondori@cea-ildefonso.edu.bo",
        None,
        "Chuma, provincia Muñecas",
        (),
    ),
    DemoUser(
        "mhuanca",
        "mantenimiento",
        "tecnico",
        "Marco Antonio",
        "Huanca",
        "Callisaya",
        "6789234",
        "LP",
        "72345678",
        None,
        "marco.huanca@example.com",
        "Comunidad Titicachi",
        (("tecnico_medio", "Técnico Medio en Electrónica", "EIS PDM", 2016),),
    ),
    DemoUser(
        "smamani",
        "mantenimiento",
        "tecnico",
        "Silvia",
        "Mamani",
        "Poma",
        "8012345",
        "LP",
        "68912345",
        None,
        None,
        "Chuma, provincia Muñecas",
        (("tecnico_superior", "Técnico Superior en Sistemas Informáticos", "UPEA", 2020),),
    ),
]

# Fechas de nacimiento coherentes con los años de egreso de cada persona.
BIRTH_DATES = {
    "rmamani": date(1979, 3, 14),
    "jchoque": date(1988, 9, 2),
    "lticona": date(2001, 6, 21),
    "pcondori": date(1975, 11, 30),
    "mhuanca": date(1994, 1, 8),
    "smamani": date(1998, 4, 17),
}

# Sensores de cada estación: (código, tipo, modelo)
SENSORS = [
    ("temp", "temperatura", "SHT31"),
    ("hum", "humedad_relativa", "SHT31"),
    ("pres", "presion_atmosferica", "BMP280"),
    ("viento", "velocidad_viento", "Anemómetro de cazoletas"),
    ("dir", "direccion_viento", "Veleta analógica"),
    ("niebla", "niebla", "Sensor óptico de niebla"),
    ("vol", "volumen_captado", "Pluviómetro de balancín"),
    ("nivel", "nivel_almacenamiento", "JSN-SR04T"),
]
UNITS = {
    "temp": "C",
    "hum": "%",
    "pres": "hPa",
    "viento": "m/s",
    "dir": "deg",
    "niebla": "%",
    "vol": "L",
    "nivel": "cm",
}

# (código, nombre, categoría, unidad, mínimo, costo unitario Bs o None si es donación)
ITEMS = [
    ("ESP32-DEVKIT", "Placa ESP32 DevKit V1", "Microcontroladores", "unidad", 1, "75"),
    ("SHT31", "Sensor de temperatura y humedad SHT31", "Sensores ambientales", "unidad", 2, "185"),
    ("BMP280", "Sensor de presión BMP280", "Sensores ambientales", "unidad", 1, "45"),
    ("ANEMOMETRO", "Anemómetro de cazoletas", "Sensores ambientales", "unidad", 1, "320"),
    ("PLUVIOMETRO", "Pluviómetro de balancín", "Sensores hídricos", "unidad", 1, "260"),
    ("JSN-SR04T", "Sensor ultrasónico impermeable JSN-SR04T", "Sensores hídricos", "unidad", 1, "95"),
    ("PANEL-20W", "Panel solar 20 W", "Energía y alimentación", "unidad", 1, "380"),
    ("BATERIA-12V", "Batería sellada 12 V 7 Ah", "Energía y alimentación", "unidad", 2, "210"),
    ("CAJA-IP65", "Caja estanca IP65", "Protección ambiental", "unidad", 2, "60"),
    ("CABLE-UTP", "Cable UTP categoría 6 exterior", "Conectividad y cableado", "metro", 20, "6.5"),
    ("MALLA-RASCHEL", "Malla Raschel 35 %", "Estructura y fijaciones", "m²", 10, "38"),
    ("ABRAZADERA", 'Abrazadera metálica 2"', "Estructura y fijaciones", "unidad", 10, "4.5"),
    ("MULTIMETRO", "Multímetro digital", "Herramientas", "unidad", 1, None),
    ("SILICONA", "Silicona selladora transparente", "Consumibles", "unidad", 3, "28"),
]


MONTHS = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]


def _month(first_day: date) -> tuple[str, date, date]:
    """Nombre, primer y último día del mes que empieza en `first_day`."""
    following = date(first_day.year + first_day.month // 12, first_day.month % 12 + 1, 1)
    return f"{MONTHS[first_day.month - 1]} {first_day.year}", first_day, following - timedelta(days=1)


def _previous_month(first_day: date) -> date:
    return date(first_day.year - (first_day.month == 1), (first_day.month - 2) % 12 + 1, 1)


def _at(day: date, hour: int = 15) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=UTC)


class DemoSeeder:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.rng = random.Random(SEED)  # noqa: S311 - simulación reproducible, no criptografía
        admin = next(
            (
                u
                for u in UserRepository(session).list(limit=1000, is_active=True)
                if any(r.name == ROLE_ADMIN for r in u.roles)
            ),
            None,
        )
        if admin is None:
            raise SeedError("No hay un administrador activo. Ejecute primero: python -m app.cli ensure-admin")
        self.admin_ctx = RequestContext(user=admin, ip="127.0.0.1")
        self.users: dict[str, User] = {}
        self.today = utcnow().date()

    def run(self) -> dict[str, int]:
        if DeviceRepository(self.session).get_by_code(MARKER_DEVICE):
            raise SeedError("La base ya tiene datos de demostración (existe el dispositivo esp32-01).")
        self._users()
        devices = self._infrastructure()
        readings = self._readings(devices)
        self._inventory()
        self._maintenance(devices)
        self._incidents(devices)
        self._recovery()
        return {"usuarios": len(self.users), "lecturas": readings}

    # --- Usuarios -------------------------------------------------------------

    def _users(self) -> None:
        roles = {r.name: r.id for r in RoleRepository(self.session).list(limit=100)}
        levels = {x.code: x.id for x in AcademicLevelRepository(self.session).list(limit=100)}
        institutions = {x.acronym: x.id for x in InstitutionRepository(self.session).list(limit=1000) if x.acronym}
        positions = {x.code: x.id for x in PositionRepository(self.session).list(limit=100)}
        service = UserService(self.session)
        for u in USERS:
            result = service.create(
                self.admin_ctx,
                username=u.username,
                role_ids=[roles[u.role]],
                password=DEMO_PASSWORD,
                profile={
                    "first_names": u.first_names,
                    "paternal_surname": u.paternal,
                    "maternal_surname": u.maternal,
                    "ci_number": u.ci,
                    "ci_complement": None,
                    "ci_issued_in": u.issued,
                    "institutional_email": u.institutional_email,
                    "personal_email": u.personal_email,
                    "mobile_phone": u.phone,
                    "birth_date": BIRTH_DATES[u.username],
                    "address": u.address,
                    "position_id": positions[u.position],
                },
                degrees=[
                    {
                        "academic_level_id": levels[level],
                        "title": title,
                        "institution_id": institutions[acronym],
                        "graduation_year": year,
                    }
                    for level, title, acronym, year in u.degrees
                ],
            )
            # Cuentas de demostración: se permite ingresar sin cambiar la contraseña.
            result.user.must_change_password = False
            self.users[u.username] = result.user
        self.session.commit()

    # --- Infraestructura y dispositivos --------------------------------------

    def _infrastructure(self) -> list:
        ctx = self.admin_ctx
        locations = location_service(self.session)
        north = locations.create(
            ctx,
            {
                "name": "Titicachi — ladera norte",
                "description": "Zona de mayor ingreso de niebla",
                "latitude": Decimal("-15.402100"),
                "longitude": Decimal("-68.938400"),
                "altitude_m": Decimal("3150"),
            },
        )
        south = locations.create(
            ctx,
            {
                "name": "Titicachi — ladera sur",
                "description": "Ladera con menor exposición al viento",
                "latitude": Decimal("-15.405300"),
                "longitude": Decimal("-68.936100"),
                "altitude_m": Decimal("3080"),
            },
        )
        cea = locations.create(
            ctx,
            {
                "name": "CEA Ildefonso de las Muñecas",
                "description": "Predio del centro educativo",
                "latitude": Decimal("-15.404000"),
                "longitude": Decimal("-68.940200"),
                "altitude_m": Decimal("3020"),
            },
        )

        fogs = fog_collector_service(self.session)
        an1 = fogs.create(
            ctx,
            {
                "code": "AN-01",
                "name": "Atrapanieblas ladera norte",
                "location_id": north.id,
                "mesh_area_m2": Decimal("40"),
                "mesh_type": "Raschel 35 %",
                "orientation": "NE",
                "installed_on": date(2026, 3, 15),
            },
        )
        an2 = fogs.create(
            ctx,
            {
                "code": "AN-02",
                "name": "Atrapanieblas ladera sur",
                "location_id": south.id,
                "mesh_area_m2": Decimal("24"),
                "mesh_type": "Raschel 35 %",
                "orientation": "E",
                "installed_on": date(2026, 5, 2),
            },
        )

        tanks = tank_service(self.session)
        tq1 = tanks.create(
            ctx,
            {
                "code": "TQ-01",
                "name": "Tanque principal",
                "location_id": cea.id,
                "fog_collector_id": an1.id,
                "capacity_liters": Decimal("5000"),
                "height_cm": Decimal("180"),
            },
        )
        tq2 = tanks.create(
            ctx,
            {
                "code": "TQ-02",
                "name": "Tanque ladera sur",
                "location_id": south.id,
                "fog_collector_id": an2.id,
                "capacity_liters": Decimal("2500"),
                "height_cm": Decimal("140"),
            },
        )

        greenhouses = greenhouse_service(self.session)
        greenhouses.create(
            ctx,
            {
                "code": "INV-01",
                "name": "Carpa solar de hortalizas",
                "location_id": cea.id,
                "area_m2": Decimal("60"),
                "tank_id": tq1.id,
            },
        )
        greenhouses.create(
            ctx,
            {
                "code": "INV-02",
                "name": "Vivero de plantines",
                "location_id": south.id,
                "area_m2": Decimal("35"),
                "tank_id": tq2.id,
            },
        )

        devices_service = DeviceService(self.session)
        sensors_service = SensorService(self.session)
        types = {t.code: t.id for t in SensorTypeRepository(self.session).list(limit=100)}
        stations = [
            ("esp32-01", "Estación ladera norte", an1, north, tq1),
            ("esp32-02", "Estación ladera sur", an2, south, tq2),
        ]
        devices = []
        for code, name, fog, location, tank in stations:
            device = devices_service.create(
                ctx,
                {
                    "code": code,
                    "name": name,
                    "description": f"Estación IoT de {fog.name.lower()}",
                    "fog_collector_id": fog.id,
                    "location_id": location.id,
                },
            ).device
            for sensor_code, type_code, model in SENSORS:
                sensors_service.create(
                    ctx,
                    {
                        "device_id": device.id,
                        "sensor_type_id": types[type_code],
                        "code": sensor_code,
                        "model": model,
                        "fog_collector_id": fog.id if type_code == "volumen_captado" else None,
                        "tank_id": tank.id if type_code == "nivel_almacenamiento" else None,
                    },
                )
            devices.append((device, fog, tank))

        spare = devices_service.create(
            ctx,
            {
                "code": "esp32-03",
                "name": "Estación de respaldo",
                "description": "Equipo de reemplazo en revisión",
                "location_id": cea.id,
            },
        ).device
        devices_service.update(ctx, spare.id, {"status": "mantenimiento"})

        calibrations = SensorCalibrationRepository(self.session)
        for device, _, _ in devices:
            for sensor in sensors_service.list(device_id=device.id):
                if sensor.code in ("hum", "vol"):
                    calibrations.add(
                        SensorCalibration(
                            sensor_id=sensor.id,
                            calibrated_at=_at(self.today - timedelta(days=45), 14),
                            offset_value=Decimal("-1.2") if sensor.code == "hum" else Decimal("0"),
                            scale_factor=Decimal("1") if sensor.code == "hum" else Decimal("1.035"),
                            notes="Calibración inicial con higrómetro de referencia"
                            if sensor.code == "hum"
                            else "Ajuste de litros por pulso con 5 L de agua medidos",
                            user_id=self.users["mhuanca"].id,
                        )
                    )
        self.session.commit()
        return devices

    # --- Lecturas simuladas ---------------------------------------------------

    def _readings(self, devices: list) -> int:
        ingestion = IngestionService(self.session)
        now = utcnow().replace(minute=0, second=0, microsecond=0)
        total = 0
        for index, (device, collector, tank) in enumerate(devices):
            area = float(collector.mesh_area_m2)
            height = float(tank.height_cm)
            level = height * (0.35 + 0.1 * index)
            regime = 0.0
            fog_on = False
            # La estación sur dejó de transmitir hace 3 horas (muestra el aviso de datos desactualizados).
            last_hour = 0 if index == 0 else 3
            readings: list[IncomingReading] = []
            for h in range(READING_DAYS * 24, last_hour - 1, -1):
                ts = now - timedelta(hours=h)
                local_hour = (ts.hour - 4) % 24
                if local_hour == 0:
                    regime = 0.7 * regime + self.rng.gauss(0, 0.7)
                night = 0.5 + 0.5 * math.cos(2 * math.pi * (local_hour - 4) / 24)
                boost = 1 / (1 + math.exp(-1.5 * regime))
                fog_on = self.rng.random() < (0.82 if fog_on else 0.04 + 0.25 * night * boost)
                fog_pct = self.rng.uniform(45, 100) if fog_on else self.rng.uniform(0, 12)
                temp = 9 + 5 * math.sin(2 * math.pi * (local_hour - 9) / 24) - 2.5 * fog_on + self.rng.gauss(0, 0.8)
                hum = min(100.0, 64 + 8 * boost + 0.3 * fog_pct + self.rng.gauss(0, 3))
                wind = max(
                    0.0, 2.6 + 2 * math.sin(2 * math.pi * (local_hour - 14) / 24) + self.rng.gammavariate(2, 0.6)
                )
                direction = (115 + self.rng.gauss(0, 30)) % 360
                pressure = 690 - 2 * regime + self.rng.gauss(0, 0.6)
                wind_eff = math.exp(-((wind - 4.5) ** 2) / (2 * 2.2**2))
                volume = area * 0.35 * (fog_pct / 100) ** 1.5 * wind_eff * max(0.0, (hum - 85) / 15) if fog_on else 0.0
                volume = round(volume * self.rng.lognormvariate(0, 0.2), 2)
                level = min(height, level + volume / float(tank.capacity_liters) * height)
                if local_hour == 7:  # riego de la mañana (consume parte de lo captado)
                    level = max(5.0, level - self.rng.uniform(0.6, 1.6))
                values = {
                    "temp": round(temp, 1),
                    "hum": round(hum, 1),
                    "pres": round(pressure, 1),
                    "viento": round(wind, 2),
                    "dir": round(direction),
                    "niebla": round(fog_pct, 1),
                    "vol": volume,
                    "nivel": round(level, 1),
                }
                # Algunas fallas realistas: sin dato y valores fuera de rango (quedan marcados, no como válidos).
                if self.rng.random() < 0.01:
                    values["viento"] = None
                if self.rng.random() < 0.004:
                    values["hum"] = 104.2
                for code, value in values.items():
                    readings.append(IncomingReading(uuid.uuid4(), code, ts, value, UNITS[code]))
            if index == 0:
                # Lectura reciente (el firmware envía cada pocos minutos): la estación norte está en línea.
                recent = utcnow().replace(second=0, microsecond=0) - timedelta(minutes=4)
                last = {r.sensor_code: r for r in readings[-len(SENSORS) :]}
                readings += [
                    IncomingReading(uuid.uuid4(), code, recent, last[code].value, UNITS[code]) for code in last
                ]
            for start in range(0, len(readings), 400):
                outcome = ingestion.ingest(
                    device,
                    batch_uid=uuid.uuid4(),
                    sent_at=readings[min(start + 399, len(readings) - 1)].measured_at,
                    firmware_version="0.1.0",
                    readings=readings[start : start + 400],
                )
                total += outcome.accepted + outcome.invalid
            if index > 0:
                device.last_seen_at = now - timedelta(hours=last_hour)
        self.session.commit()
        return total

    # --- Inventario periódico -------------------------------------------------

    def _inventory(self) -> None:
        ctx = self.admin_ctx
        inventory = InventoryService(self.session)
        periods = InventoryPeriodService(self.session)
        categories = {c.name: c.id for c in inventory.list_categories()}
        items = {}
        for code, name, category, unit, minimum, _ in ITEMS:
            items[code] = inventory.create_item(
                ctx,
                {
                    "code": code,
                    "name": name,
                    "category_id": categories[category],
                    "unit": unit,
                    "min_stock": Decimal(minimum),
                    "condition": "nuevo",
                    "storage_location": "Depósito del CEA",
                },
                initial_stock=Decimal(0),
                device_ids=[],
                sensor_ids=[],
            )
        cost = {code: (Decimal(c) if c is not None else None) for code, *_, c in ITEMS}

        def move(code: str, kind: str, qty: str, reason: str, day: date) -> None:
            inventory.apply_movement(
                ctx,
                items[code].id,
                kind,
                Decimal(qty),
                reason,
                unit_cost=cost[code] if kind == "entrada" else None,
                occurred_at=_at(day),
            )

        # Dos meses anteriores (se cierran con conteo físico) y el mes en curso (abierto).
        current_first = self.today.replace(day=1)
        second_first = _previous_month(current_first)
        first_first = _previous_month(second_first)
        name1, start1, end1 = _month(first_first)
        name2, start2, end2 = _month(second_first)
        name3, start3, end3 = _month(current_first)
        august = periods.create(ctx, name=name1, start_date=start1, end_date=end1, notes=None)
        september = periods.create(ctx, name=name2, start_date=start2, end_date=end2, notes=None)

        def day_of(start: date, n: int) -> date:
            # Nunca en el futuro: en el mes en curso se limita a hoy.
            return min(start + timedelta(days=n - 1), self.today)

        # Agosto: compra inicial (adquisición del proyecto) y primeras salidas.
        for code, *_ in ITEMS:
            qty = {
                "CABLE-UTP": "100",
                "MALLA-RASCHEL": "40",
                "ABRAZADERA": "30",
                "SILICONA": "6",
                "BATERIA-12V": "4",
            }.get(code, "3")
            reason = "Donación de la comunidad" if cost[code] is None else "Compra inicial del proyecto"
            move(code, "entrada", qty, reason, day_of(start1, 5))
        move("CABLE-UTP", "salida", "35", "Tendido de cable a la estación norte", day_of(start1, 12))
        move("ABRAZADERA", "salida", "12", "Fijación de postes del atrapanieblas", day_of(start1, 14))
        move("SILICONA", "salida", "2", "Sellado de cajas estancas", day_of(start1, 20))
        self.session.commit()

        count_aug = {code: None for code, *_ in ITEMS}
        count_aug.update({"CABLE-UTP": "63", "ABRAZADERA": "18"})  # faltan 2 m de cable
        self._count_and_close(periods, august, items, count_aug)

        # Septiembre
        move("SHT31", "entrada", "2", "Reposición de sensores", day_of(start2, 8))
        move("MALLA-RASCHEL", "salida", "16", "Malla para el atrapanieblas AN-02", day_of(start2, 10))
        move("BATERIA-12V", "salida", "1", "Batería de la estación sur", day_of(start2, 18))
        move("CABLE-UTP", "salida", "25", "Tendido de cable a la estación sur", day_of(start2, 22))
        self.session.commit()
        count_sep = {code: None for code, *_ in ITEMS}
        count_sep.update({"ABRAZADERA": "19"})  # sobra 1 abrazadera
        self._count_and_close(periods, september, items, count_sep)

        # Mes en curso (abierto): movimientos del mes y conteo parcial.
        october = periods.create(
            ctx, name=name3, start_date=start3, end_date=end3, notes=f"Conteo físico previsto para el {end3:%d/%m/%Y}"
        )
        move("SILICONA", "entrada", "4", "Compra en feria de Chuma", day_of(start3, 3))
        move("CAJA-IP65", "salida", "1", "Caja para la estación de respaldo", day_of(start3, 7))
        self.session.commit()
        periods.register_counts(
            ctx,
            october.id,
            [
                {"item_id": items["ESP32-DEVKIT"].id, "counted_quantity": Decimal(3)},
                {"item_id": items["PANEL-20W"].id, "counted_quantity": Decimal(3)},
            ],
        )
        self.items = items

    def _count_and_close(self, periods: InventoryPeriodService, period, items: dict, counted: dict) -> None:
        summary = periods.summary(period.id)
        entries = []
        for balance in summary.balances:
            override = counted.get(balance.item.code)
            quantity = Decimal(override) if override is not None else balance.theoretical_quantity
            entries.append({"item_id": balance.item.id, "counted_quantity": quantity})
        periods.register_counts(self.admin_ctx, period.id, entries)
        periods.close(self.admin_ctx, period.id)

    # --- Mantenimiento --------------------------------------------------------

    def _maintenance(self, devices: list) -> None:
        sensors = SensorService(self.session)
        north, south = devices[0][0], devices[1][0]
        sensor = {(s.device_id, s.code): s.id for s in sensors.list()}
        tech1 = RequestContext(user=self.users["mhuanca"])
        tech2 = RequestContext(user=self.users["smamani"])
        service = MaintenanceService(self.session)
        records = [
            (
                tech1,
                north,
                None,
                20,
                "inspeccion",
                "Inspección general de la estación y del atrapanieblas norte.",
                "operativo",
                [],
            ),
            (
                tech2,
                south,
                ("vol"),
                9,
                "limpieza",
                "Limpieza del pluviómetro de balancín; tenía residuos de hojas.",
                "operativo",
                [],
            ),
            (
                tech1,
                north,
                ("hum"),
                6,
                "calibracion",
                "Verificación de humedad con higrómetro de referencia; desvío dentro de tolerancia.",
                "operativo",
                [],
            ),
            (
                tech2,
                south,
                ("temp"),
                4,
                "reemplazo",
                "Reemplazo del sensor SHT31 por lecturas erráticas tras una helada.",
                "operativo",
                [UsedPart(self.items["SHT31"].id, Decimal(1)), UsedPart(self.items["SILICONA"].id, Decimal(1))],
            ),
            (
                tech1,
                north,
                None,
                2,
                "correctivo",
                "Ajuste de abrazaderas y reparación de un tramo de malla dañado por el viento.",
                "operativo_con_observaciones",
                [
                    UsedPart(self.items["ABRAZADERA"].id, Decimal(4)),
                    UsedPart(self.items["MALLA-RASCHEL"].id, Decimal(2)),
                ],
            ),
        ]
        for ctx, device, sensor_code, days_ago, kind, description, final, parts in records:
            service.register(
                ctx,
                device_id=device.id,
                sensor_id=sensor[(device.id, sensor_code)] if sensor_code else None,
                performed_at=utcnow() - timedelta(days=days_ago, hours=3),
                maintenance_type=kind,
                description=description,
                final_status=final,
                parts=parts,
            )

    # --- Reportes de incidencia ------------------------------------------------

    def _incidents(self, devices: list) -> None:
        """Un reporte en cada etapa del flujo: abierto, aceptado, en progreso y finalizado."""
        north, south = devices[0][0], devices[1][0]
        sensor = {(s.device_id, s.code): s.id for s in SensorService(self.session).list()}
        ctx = {
            name: RequestContext(user=self.users[name])
            for name in ("jchoque", "lticona", "rmamani", "mhuanca", "smamani")
        }
        service = IncidentService(self.session)

        def report(who: str, title: str, description: str, priority: str, device, sensor_code=None, place=None):
            return service.report(
                ctx[who],
                title=title,
                description=description,
                priority=priority,
                location_reference=place,
                device_id=device.id,
                sensor_id=sensor[(device.id, sensor_code)] if sensor_code else None,
            )

        report(
            "jchoque",
            "Malla rota en el atrapanieblas sur",
            "Después del viento de anoche la malla tiene un desgarro de casi un metro en la parte superior.",
            "alta",
            south,
            place="Atrapanieblas sur, ladera junto al invernadero",
        )
        accepted = report(
            "lticona",
            "El nivel del tanque no se actualiza",
            "En el resumen general el nivel del tanque norte muestra el mismo valor desde hace dos días.",
            "media",
            north,
            "nivel",
        )
        service.accept(ctx["mhuanca"], accepted.id)

        in_progress = report(
            "jchoque",
            "Caja de la estación norte con humedad",
            "Al abrir la caja de la estación se ven gotas en la tapa y el cable de alimentación húmedo.",
            "alta",
            north,
            place="Poste de la estación norte",
        )
        service.accept(ctx["smamani"], in_progress.id)
        service.start(ctx["smamani"], in_progress.id)

        finished = report(
            "lticona",
            "Pluviómetro sur con hojas",
            "Los estudiantes vieron hojas y tierra dentro del pluviómetro del atrapanieblas sur.",
            "baja",
            south,
            "vol",
        )
        service.accept(ctx["mhuanca"], finished.id)
        service.start(ctx["mhuanca"], finished.id)
        service.finish(
            ctx["mhuanca"],
            finished.id,
            device_id=south.id,
            sensor_id=sensor[(south.id, "vol")],
            maintenance_type="limpieza",
            description="Limpieza del balancín y del embudo; se verificó el conteo de pulsos con agua medida.",
            final_status="operativo",
            parts=[],
        )

        sealed = report(
            "rmamani",
            "Revisar el sellado de la caja sur",
            "Antes de la época de lluvias conviene revisar el sellado de la caja de la estación sur.",
            "media",
            south,
        )
        service.accept(ctx["smamani"], sealed.id)
        service.start(ctx["smamani"], sealed.id)
        service.finish(
            ctx["smamani"],
            sealed.id,
            device_id=south.id,
            sensor_id=None,
            maintenance_type="preventivo",
            description="Se renovó el sellado de la tapa y de los prensaestopas con silicona.",
            final_status="operativo",
            parts=[UsedPart(self.items["SILICONA"].id, Decimal(1))],
        )

    # --- Recuperación de cuentas ---------------------------------------------

    def _recovery(self) -> None:
        recovery = RecoveryService(self.session)
        recovery.submit(
            RequestContext(user=None, ip="192.168.1.34"), "lticona", "Olvidé mi contraseña después de vacaciones."
        )
        recovery.submit(RequestContext(user=None, ip="192.168.1.51"), "pcondori", None)
        recovery.submit(
            RequestContext(user=None, ip="192.168.1.77"), "usuario.desconocido", "Necesito acceso al sistema."
        )
        pending = recovery.list(offset=0, limit=10, status="pendiente")[0]
        unknown = next(r for r in pending if r.username_requested == "usuario.desconocido")
        recovery.reject(self.admin_ctx, unknown.id, reason="No corresponde a un usuario registrado del CEA.")
