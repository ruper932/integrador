"""Pruebas unitarias de las 5 funciones más críticas del sistema (patrón Arrange-Act-Assert).

Cada función se prueba aislada: sin base de datos ni red. El servicio de inventario recibe
dobles de prueba (unittest.mock) en lugar de sus repositorios.

1. InventoryService.apply_movement  -> no se retira más stock del disponible.
2. assess_value                     -> calidad de la lectura IoT; lo no medido es None, nunca 0.
3. hash_password / verify_password  -> contraseñas guardadas solo como hash seguro.
4. firmware_version                 -> solo se acepta firmware ESP32 válido para OTA.
5. predict                          -> el modelo ML no inventa predicciones sin datos suficientes.
"""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from app.business.ml.inference import predict
from app.business.rules.firmware import MAX_IMAGE_BYTES, firmware_version
from app.business.rules.measurements import assess_value
from app.business.services.context import RequestContext
from app.business.services.inventory_service import InventoryService
from app.core.errors import BusinessRuleError
from app.core.security import hash_password, verify_password
from app.data.models.iot import SensorType

# ---------------------------------------------------------------------------
# 1. InventoryService.apply_movement
# ---------------------------------------------------------------------------


def inventory_service(stock: str, direction: int) -> tuple[InventoryService, SimpleNamespace]:
    """Servicio con repositorios simulados: un repuesto con `stock` y un tipo de movimiento."""
    service = InventoryService.__new__(InventoryService)  # sin sesión de base de datos
    item = SimpleNamespace(id=1, code="BME280", unit="unidad", current_stock=Decimal(stock), is_active=True)
    service.tz = ZoneInfo("America/La_Paz")
    service.items = MagicMock(get_for_update=MagicMock(return_value=item))
    movement_type = SimpleNamespace(id=2, code="salida", direction=direction, manual_allowed=True)
    service.movement_types = MagicMock(get_by_code=MagicMock(return_value=movement_type))
    service.periods = MagicMock(closed_containing=MagicMock(return_value=None))
    service.movements = MagicMock(add=MagicMock(side_effect=lambda movement: movement))
    service.audit = MagicMock()
    return service, item


TECNICO = RequestContext(user=SimpleNamespace(id=7))


class TestApplyMovement:
    def test_salida_descuenta_el_stock_y_registra_el_movimiento(self):
        # Arrange
        service, item = inventory_service(stock="5", direction=-1)
        # Act
        movement = service.apply_movement(TECNICO, 1, "salida", Decimal("2"), "Reemplazo de sensor")
        # Assert
        assert item.current_stock == Decimal("3")
        assert (movement.stock_before, movement.stock_after) == (Decimal("5"), Decimal("3"))
        assert movement.user_id == 7
        service.audit.record.assert_called_once()

    def test_salida_mayor_al_stock_se_rechaza_sin_modificar_nada(self):
        # Arrange
        service, item = inventory_service(stock="1", direction=-1)
        # Act
        with pytest.raises(BusinessRuleError) as error:
            service.apply_movement(TECNICO, 1, "salida", Decimal("3"), "Reemplazo de sensor")
        # Assert
        assert error.value.code == "stock_insuficiente"
        assert item.current_stock == Decimal("1")
        service.movements.add.assert_not_called()

    def test_entrada_aumenta_el_stock(self):
        # Arrange
        service, item = inventory_service(stock="1", direction=1)
        # Act
        service.apply_movement(TECNICO, 1, "entrada", Decimal("4"), "Compra")
        # Assert
        assert item.current_stock == Decimal("5")

    @pytest.mark.parametrize("quantity", [Decimal("0"), Decimal("-2")])
    def test_cantidad_no_positiva_se_rechaza(self, quantity):
        # Arrange
        service, _ = inventory_service(stock="5", direction=-1)
        # Act
        with pytest.raises(BusinessRuleError) as error:
            service.apply_movement(TECNICO, 1, "salida", quantity, "Error de digitación")
        # Assert
        assert error.value.code == "cantidad_invalida"

    def test_movimiento_sin_usuario_responsable_se_rechaza(self):
        # Arrange
        service, _ = inventory_service(stock="5", direction=-1)
        anonimo = RequestContext(user=None)
        # Act
        with pytest.raises(BusinessRuleError) as error:
            service.apply_movement(anonimo, 1, "salida", Decimal("1"), "Sin responsable")
        # Assert
        assert error.value.code == "usuario_requerido"


# ---------------------------------------------------------------------------
# 2. assess_value
# ---------------------------------------------------------------------------

HUMEDAD = SensorType(
    code="humedad_relativa", name="Humedad relativa", unit="%", min_value=0, max_value=100, aggregation="instantaneo"
)


class TestAssessValue:
    def test_lectura_dentro_del_rango_es_valida(self):
        # Arrange
        value, unit = 87.5, "%"
        # Act
        result = assess_value(HUMEDAD, value, unit)
        # Assert
        assert result.quality == "valida"
        assert result.detail is None

    def test_variable_no_medida_se_registra_como_sin_dato_y_no_como_cero(self):
        # Arrange
        value = None  # el sensor no respondió
        # Act
        result = assess_value(HUMEDAD, value, "%")
        # Assert
        assert result.quality == "sin_dato"

    @pytest.mark.parametrize("value", [-0.1, 100.1])
    def test_valor_fisicamente_imposible_queda_fuera_de_rango(self, value):
        # Arrange: la humedad relativa solo existe entre 0 y 100 %
        # Act
        result = assess_value(HUMEDAD, value, "%")
        # Assert
        assert result.quality == "fuera_de_rango"
        assert "[0, 100]" in result.detail

    def test_unidad_distinta_a_la_del_sensor_se_marca(self):
        # Arrange
        value, unit = 50.0, "pct"
        # Act
        result = assess_value(HUMEDAD, value, unit)
        # Assert
        assert result.quality == "unidad_invalida"

    @pytest.mark.parametrize("value", [float("nan"), float("inf")])
    def test_valor_no_finito_es_invalido(self, value):
        # Arrange: NaN/infinito llegan cuando el sensor falla a mitad de la lectura
        # Act
        result = assess_value(HUMEDAD, value, "%")
        # Assert
        assert result.quality == "invalida"


# ---------------------------------------------------------------------------
# 3. hash_password / verify_password
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    def test_contrasena_correcta_se_verifica(self):
        # Arrange
        stored = hash_password("Atrapanieblas-2026")
        # Act
        ok = verify_password("Atrapanieblas-2026", stored)
        # Assert
        assert ok is True

    def test_contrasena_incorrecta_no_se_verifica(self):
        # Arrange
        stored = hash_password("Atrapanieblas-2026")
        # Act
        ok = verify_password("atrapanieblas-2026", stored)
        # Assert
        assert ok is False

    def test_el_hash_no_contiene_la_contrasena_y_usa_sal_aleatoria(self):
        # Arrange
        password = "Atrapanieblas-2026"
        # Act
        first, second = hash_password(password), hash_password(password)
        # Assert
        assert password not in first
        assert first.startswith("scrypt$")
        assert first != second

    @pytest.mark.parametrize("stored", ["", "texto-plano", "md5$abc$def", "scrypt$x$y$z$no-base64$!!"])
    def test_hash_danado_o_de_otro_algoritmo_no_autentica(self, stored):
        # Arrange: valor almacenado corrupto o heredado
        # Act
        ok = verify_password("Atrapanieblas-2026", stored)
        # Assert
        assert ok is False


# ---------------------------------------------------------------------------
# 4. firmware_version
# ---------------------------------------------------------------------------


def esp32_image(marker: bytes = b"ATINA-FW:0.2.0;", chip_id: int = 0x0000, size: int = 4096) -> bytes:
    """Imagen mínima con la cabecera de ESP-IDF: byte mágico 0xE9 y chip id en los bytes 12-13."""
    header = bytes([0xE9]) + bytes(11) + chip_id.to_bytes(2, "little") + bytes(10)
    return (header + marker).ljust(size, b"\xff")


class TestFirmwareVersion:
    def test_imagen_valida_devuelve_la_version_compilada(self):
        # Arrange
        image = esp32_image(marker=b"ATINA-FW:0.2.0;")
        # Act
        version = firmware_version(image)
        # Assert
        assert version == "0.2.0"

    @pytest.mark.parametrize(
        ("image", "code"),
        [
            (b"\x00" * 4096, "firmware_invalido"),  # no es una imagen de ESP32 (falta 0xE9)
            (esp32_image(chip_id=0x0009), "firmware_chip"),  # compilada para ESP32-S3
            (esp32_image(marker=b""), "firmware_sin_version"),  # no es firmware ATINA
            (esp32_image(marker=b"ATINA-FW:0.1.0;ATINA-FW:0.2.0;"), "firmware_sin_version"),  # versión ambigua
            (esp32_image(size=MAX_IMAGE_BYTES + 1), "firmware_muy_grande"),  # no cabe en la ranura OTA
        ],
        ids=["sin_cabecera_esp32", "otro_chip", "sin_marca_atina", "version_ambigua", "excede_ranura_ota"],
    )
    def test_imagen_invalida_se_rechaza_con_motivo(self, image, code):
        # Arrange: parámetros
        # Act
        with pytest.raises(BusinessRuleError) as error:
            firmware_version(image)
        # Assert
        assert error.value.code == code


# ---------------------------------------------------------------------------
# 5. predict
# ---------------------------------------------------------------------------

FEATURES = ["volumen_dia", "humedad_media", "temperatura_media", "viento_medio"]


class ModeloFalso:
    """Sustituye al modelo entrenado: devuelve un valor fijo y guarda lo que recibió."""

    def __init__(self, value: float) -> None:
        self.value = value
        self.received: pd.DataFrame | None = None

    def predict(self, frame: pd.DataFrame) -> list[float]:
        self.received = frame
        return [self.value]


def artifact(value: float) -> dict:
    return {"features": FEATURES, "model": ModeloFalso(value), "metadata": {"version_modelo": "sim-0.1.0"}}


class TestPredict:
    def test_con_datos_completos_genera_la_prediccion(self):
        # Arrange
        model = artifact(12.3456)
        row = pd.Series({"volumen_dia": 10.0, "humedad_media": 92.0, "temperatura_media": 9.5, "viento_medio": 3.1})
        # Act
        result = predict(model, row, "2026-11-13")
        # Assert
        assert result["estado"] == "generada"
        assert result["resultado_litros"] == 12.35
        assert result["version_modelo"] == "sim-0.1.0"
        assert result["fecha_predicha"] == "2026-11-13"
        assert list(model["model"].received.columns) == FEATURES

    def test_sin_variable_obligatoria_informa_datos_insuficientes(self):
        # Arrange: sin volumen del día no se predice
        model = artifact(12.0)
        row = pd.Series({"volumen_dia": None, "humedad_media": 92.0, "temperatura_media": 9.5, "viento_medio": 3.1})
        # Act
        result = predict(model, row, "2026-11-13")
        # Assert
        assert result["estado"] == "datos_insuficientes"
        assert result["resultado_litros"] is None
        assert result["faltantes"] == ["volumen_dia"]
        assert model["model"].received is None  # el modelo ni siquiera se ejecuta

    def test_demasiadas_variables_faltantes_informa_datos_insuficientes(self):
        # Arrange: 2 de 4 variables faltan (50 % > 30 % permitido)
        model = artifact(12.0)
        row = pd.Series({"volumen_dia": 10.0, "humedad_media": 92.0})
        # Act
        result = predict(model, row, "2026-11-13")
        # Assert
        assert result["estado"] == "datos_insuficientes"
        assert result["faltantes"] == ["temperatura_media", "viento_medio"]

    def test_estimacion_negativa_se_acota_a_cero_litros(self):
        # Arrange: un regresor puede devolver valores negativos
        model = artifact(-3.7)
        row = pd.Series({"volumen_dia": 0.0, "humedad_media": 40.0, "temperatura_media": 18.0, "viento_medio": 1.0})
        # Act
        result = predict(model, row, "2026-11-13")
        # Assert
        assert result["estado"] == "generada"
        assert result["resultado_litros"] == 0.0
