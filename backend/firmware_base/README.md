# Imágenes base para la primera instalación del ESP32

El módulo **Firmware de estaciones → Primera instalación** escribe por USB, desde el navegador, estas
imágenes junto con el `firmware.bin` de la versión elegida. Son fijas para la plataforma del proyecto
(`espressif32@6.9.0`, placa `esp32dev`, tabla de particiones por defecto con dos ranuras OTA):

| Archivo          | Dirección | Origen |
|------------------|-----------|--------|
| `bootloader.bin` | `0x1000`  | `firmware/.pio/build/esp32dev/bootloader.bin` (tras `pio run`) |
| `partitions.bin` | `0x8000`  | `firmware/.pio/build/esp32dev/partitions.bin` |
| `boot_app0.bin`  | `0xE000`  | `~/.platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin` |
| `firmware.bin`   | `0x10000` | la versión cargada en el sistema (no se guarda aquí) |

Si se cambia la plataforma, la placa o la tabla de particiones en `firmware/platformio.ini`, compile con
`pio run` y vuelva a copiar los tres archivos. No contienen credenciales: la configuración de cada
estación se escribe después, por el puerto serie, en la memoria NVS.
