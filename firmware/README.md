# Firmware de la estación IoT (ESP32)

PlatformIO + framework Arduino. Envía mediciones por HTTP/JSON a la API local
(`POST /api/v1/iot/measurements/batch`).

## Compilar y cargar

```bash
pio run                 # compilar
pio run -t upload       # cargar en el ESP32
pio device monitor      # consola serie (115200 baudios)
```

## Configuración segura (sin credenciales en el código)

Las credenciales se guardan en la memoria NVS del ESP32. Con el monitor serie abierto:

```text
set ssid RedInstitucional
set wifi_pass ********
set api_url http://192.168.1.10/api/v1/iot/measurements/batch
set device_id esp32-01
set device_key dk_...           # se muestra una sola vez al registrar el dispositivo en el sistema
set ntp 192.168.1.10            # servidor NTP de la red local
set sample_s 60                 # intervalo de muestreo inicial (5–3600 s); luego lo fija el sistema web
save
```

`show` muestra la configuración sin revelar la API key; `clear` la borra.

## Sensores y códigos

Los códigos deben coincidir con los sensores registrados para el dispositivo en el sistema.

| Código   | Variable               | Unidad | Hardware sugerido            |
|----------|------------------------|--------|------------------------------|
| `temp`   | Temperatura            | C      | BME280 (I²C 0x76, GPIO 27/26); respaldo DHT11 |
| `hum`    | Humedad relativa       | %      | BME280; respaldo DHT11 (GPIO 25) |
| `pres`   | Presión atmosférica    | hPa    | BME280                       |
| `vol`    | Volumen captado        | L      | Pluviómetro de balancín / caudalímetro (pulsos, GPIO 32) |
| `nivel`  | Nivel del tanque       | cm     | JSN-SR04T (GPIO 18/19)       |
| `niebla` | Intensidad de niebla   | %      | Opcional (`-DHAS_FOG_SENSOR=1`, GPIO 34) |

- **Volumen incremental**: cada lectura de `vol` son los litros captados desde la lectura anterior
  (`pulsos × LITERS_PER_PULSE`). Calibrar `LITERS_PER_PULSE` en `include/config.h`.
- Un sensor ausente o con fallo se envía con `"value": null`, nunca `0`.

## Funcionamiento sin conexión

- Cada lectura se guarda primero en `LittleFS` (`/pending.jsonl`) con un `message_id` UUID.
- Al haber conexión se envían lotes de 50; solo se eliminan cuando el servidor responde 200.
  Un reenvío del mismo dato no genera duplicados (el servidor descarta `message_id` repetidos).
- Sin hora sincronizada (NTP) no se registran lecturas; los pulsos de volumen se siguen acumulando.
- LED (GPIO 2): fijo = comunicación correcta; parpadeo = más de 30 min sin confirmar envíos.
  La consola serie también informa la pérdida de comunicación y la cantidad de lecturas pendientes.

Conexiones detalladas, esquema y recomendaciones de instalación: `docs/conexiones_sensores_esp32.md`.

## Actualización por la red (OTA)

La primera vez el ESP32 se programa por USB: desde el sistema (**Firmware de estaciones → Primera
instalación por USB**, en Chrome o Edge por `https://`), que escribe el bootloader, las particiones y la
versión elegida y luego envía la configuración por el puerto serie; o con `pio run -t upload` y la consola
serie. Las imágenes base están en `backend/firmware_base/` (ver su README si cambia la plataforma). Desde la
versión 0.2.0 las siguientes se instalan desde el sistema, en **Operaciones → Firmware de estaciones** (administrador y
personal de mantenimiento):

1. Aumentar `FIRMWARE_VERSION` en `include/config.h` y compilar con `pio run`.
2. Cargar `.pio/build/esp32dev/firmware.bin` en el sistema. La versión se lee del propio archivo
   (marca `ATINA-FW:<versión>;`), así coincide siempre con la que informa el ESP32.
3. Asignar la versión a una estación de prueba; si sigue enviando datos, extenderla al resto.

Cada estación consulta `GET /api/v1/iot/firmware` con su propia credencial después de un muestreo,
al arrancar y luego como máximo una vez por hora. Si el sistema le asignó una versión distinta de la
que ejecuta, la descarga, verifica el MD5, la instala y se reinicia. Las lecturas pendientes están
en LittleFS y no se pierden; solo se pierden los pulsos de volumen de los segundos de la descarga.
Para volver atrás, se asigna la versión anterior.

## Prueba en banco

`pruebas/prueba_sensores.cpp` es el sketch con el que se probaron el DHT y el BME280: crea su propia
red Wi-Fi y guarda un CSV. No se compila con el firmware.


## Intervalo de muestreo desde el sistema (firmware 0.3.0)

En **Monitoreo en vivo** se elige el muestreo de cada estación: «Tiempo real» (5 s), cada 30 s o cada minuto.
El servidor lo devuelve en la respuesta de cada lote (`sample_interval_s`); la estación lo aplica desde el ciclo
siguiente y lo guarda en la memoria no volátil, así que se mantiene tras un reinicio. Las estaciones con
firmware anterior a 0.3.0 ignoran ese campo y siguen con su `sample_s`.
