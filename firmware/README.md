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
set sample_s 300                # intervalo de muestreo en segundos
save
```

`show` muestra la configuración sin revelar la API key; `clear` la borra.

## Sensores y códigos

Los códigos deben coincidir con los sensores registrados para el dispositivo en el sistema.

| Código   | Variable               | Unidad | Hardware sugerido            |
|----------|------------------------|--------|------------------------------|
| `temp`   | Temperatura            | C      | SHT31 (I²C 0x44)             |
| `hum`    | Humedad relativa       | %      | SHT31                        |
| `pres`   | Presión atmosférica    | hPa    | BMP280 (I²C 0x76)            |
| `vol`    | Volumen captado        | L      | Pluviómetro de balancín / caudalímetro (pulsos, GPIO 27) |
| `nivel`  | Nivel del tanque       | cm     | JSN-SR04T (GPIO 25/26)       |
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
