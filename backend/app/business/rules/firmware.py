"""Validación de imágenes de firmware de la estación (ESP32) antes de aceptarlas para OTA.

La versión no se escribe a mano: se lee de la marca «ATINA-FW:<versión>;» que el firmware lleva
compilada. Así la versión cargada coincide siempre con la que el ESP32 informa al arrancar y la
estación no vuelve a descargar la misma imagen en bucle.
"""

import re

from app.core.errors import BusinessRuleError

# Ranura de aplicación de la tabla de particiones por defecto del ESP32 con 4 MB (app0/app1 = 0x140000).
MAX_IMAGE_BYTES = 0x140000
_IMAGE_MAGIC = 0xE9  # primer byte de toda imagen de aplicación de ESP-IDF
_CHIP_ID_ESP32 = 0x0000  # ESP32 clásico (ESP32-S2/S3/C3 usan otros valores)
_MARKER = re.compile(rb"ATINA-FW:([0-9A-Za-z.+-]{1,32});")


def firmware_version(image: bytes) -> str:
    """Devuelve la versión de una imagen válida o rechaza el archivo con un motivo claro."""
    if len(image) > MAX_IMAGE_BYTES:
        raise BusinessRuleError(
            f"El archivo supera el tamaño máximo de una ranura OTA ({MAX_IMAGE_BYTES} bytes).",
            code="firmware_muy_grande",
        )
    if len(image) < 24 or image[0] != _IMAGE_MAGIC:
        raise BusinessRuleError(
            "El archivo no es una imagen de aplicación para ESP32 (use el firmware.bin generado por PlatformIO).",
            code="firmware_invalido",
        )
    if int.from_bytes(image[12:14], "little") != _CHIP_ID_ESP32:
        raise BusinessRuleError(
            "La imagen fue compilada para otro modelo de chip, no para ESP32.", code="firmware_chip"
        )
    versions = {m.group(1).decode() for m in _MARKER.finditer(image)}
    if len(versions) != 1:
        raise BusinessRuleError(
            "No se encontró la versión del firmware de la estación ATINA en el archivo.", code="firmware_sin_version"
        )
    return versions.pop()
