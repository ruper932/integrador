# Conexiones de los sensores al ESP32

> Estación meteorológica con **DHT11** y **BME280**, más los sensores de agua del atrapanieblas.
> Placa: **ESP32 DevKit V1** (`esp32dev` en PlatformIO), lógica de **3,3 V**.
> Los pines están definidos en `firmware/include/config.h`. Si se cambia una conexión, hay que cambiar
> también ese archivo y volver a compilar.

---

## Resumen de pines

| Sensor | Pin del sensor | Pin del ESP32 | Notas |
|---|---|---|---|
| **BME280** (I²C) | VCC / VIN | **3V3** | |
| | GND | **GND** | |
| | SDA | **GPIO 27** | Datos I²C |
| | SCL | **GPIO 26** | Reloj I²C |
| | SDO (si el módulo lo tiene) | **GND** | Dirección 0x76, la que usa el firmware |
| | CSB (si el módulo lo tiene) | **3V3** | Fuerza el modo I²C |
| **DHT11** | VCC (+) | **3V3** | |
| | DATA (OUT) | **GPIO 25** | Resistencia de 10 kΩ entre DATA y 3V3 si el sensor no la trae |
| | GND (−) | **GND** | |
| Pluviómetro de balancín (volumen) | Terminal 1 | **GPIO 32** | Interruptor reed; el firmware activa el pull-up interno |
| | Terminal 2 | **GND** | |
| JSN-SR04T (nivel del tanque) | 5V | **VIN (5 V)** | |
| | GND | **GND** | |
| | TRIG | **GPIO 18** | |
| | ECHO | **GPIO 19** mediante **divisor de tensión** | ECHO entrega 5 V: ver más abajo |
| Sensor de niebla (opcional) | Salida analógica | **GPIO 34** | Máximo 3,3 V; activar con `-DHAS_FOG_SENSOR=1` |
| LED de estado | — | **GPIO 2** | LED integrado de la placa |

Los pines de la estación meteorológica (GPIO 25, 26 y 27) son los mismos del prototipo probado en
banco (`firmware/pruebas/prueba_sensores.cpp`). Por eso el pluviómetro y el sensor de nivel pasaron
a GPIO 32, 18 y 19.

---

## Esquema

```text
                         ESP32 DevKit V1
                     ┌───────────────────────┐
   BME280 VCC ───────┤ 3V3               VIN ├──────── JSN-SR04T 5V
   DHT11  VCC ───────┤ 3V3                   │
   BME280 GND ───────┤ GND               GND ├──────── JSN-SR04T GND, pluviómetro (terminal 2)
   DHT11  GND ───────┤ GND                   │
   BME280 SDA ───────┤ GPIO 27       GPIO 18 ├──────── JSN-SR04T TRIG
   BME280 SCL ───────┤ GPIO 26       GPIO 19 ├──┬───── JSN-SR04T ECHO (por R1 = 1 kΩ)
   DHT11 DATA ──┬────┤ GPIO 25               │  └─ R2 = 2 kΩ ── GND
                │    │               GPIO 32 ├──────── pluviómetro (terminal 1)
     10 kΩ a 3V3     │               GPIO 34 ├──────── sensor de niebla (opcional)
                     │               GPIO 2  ├── LED integrado
                     └───────────────────────┘
```

### Divisor de tensión para el ECHO del JSN-SR04T

El JSN-SR04T alimentado a 5 V devuelve un pulso de 5 V, y los pines del ESP32 admiten como máximo
3,3 V:

```text
ECHO ──[ R1 = 1 kΩ ]──┬── GPIO 19
                      │
                  [ R2 = 2 kΩ ]
                      │
                     GND        → 5 V × 2 / (1 + 2) ≈ 3,3 V
```

---

## Qué mide cada sensor y cómo se combinan

| Variable (código en el sistema) | Fuente principal | Respaldo | Unidad |
|---|---|---|---|
| Temperatura (`temp`) | BME280 | DHT11 | °C |
| Humedad relativa (`hum`) | BME280 | DHT11 | % |
| Presión atmosférica (`pres`) | BME280 | — | hPa |

- El firmware usa el **BME280** cuando responde. Es más preciso y, sobre todo, mide la humedad hasta
  el **100 %**, que es justo el rango donde hay niebla.
- El **DHT11** cubre la temperatura y la humedad si el BME280 deja de responder: cable suelto,
  humedad en el conector o sensor dañado. En el ciclo siguiente el firmware intenta reconectar el
  BME280.
- Si ninguno responde, la lectura se envía como `null`, **nunca como 0**.
- La placa no puede leer la humedad de un **BMP280** vendido como BME280. El firmware lo detecta
  (identificador de chip `0x58` en vez de `0x60`) y toma la humedad del DHT11. Al arrancar, la consola
  serie lo indica así: `BME280: ok (BMP280, sin humedad)`.

| Sensor | Rango | Precisión típica | Observación |
|---|---|---|---|
| BME280 | −40 a 85 °C · 0 a 100 % HR · 300 a 1100 hPa | ±1 °C · ±3 % HR · ±1 hPa | |
| DHT11 | 0 a 50 °C · 20 a 90 % HR | ±2 °C · ±5 % HR | **No distingue niebla:** por encima de ~90 % se satura. Lee como máximo una vez por segundo. |

Si se reemplaza el DHT11 por un **DHT22**, que tiene rango completo y es más preciso, se compila con
`-DDHT_TYPE=DHT22`. Las conexiones son las mismas.

---

## Recomendaciones de instalación

- **Abrigo ventilado:** el BME280 y el DHT11 deben ir en un abrigo meteorológico (tipo Stevenson o
  platos apilados), **fuera** de la caja del ESP32 y protegidos del sol directo. Dentro de una caja
  cerrada, el calor de la placa y del sol falsea la temperatura: el prototipo registró picos de unos
  46 °C.
- **Cable I²C corto:** mantener el BME280 a menos de ~1 m del ESP32. Para distancias mayores, usar
  cable trenzado y bajar la velocidad del bus.
- **DHT11 a distancia:** con cables de más de ~5 m, usar la resistencia de 10 kΩ (o una de 4,7 kΩ).
- **Conectores** protegidos de la humedad: la niebla condensa en todo.
- **Pluviómetro:** si el balancín genera pulsos dobles, se puede agregar un condensador de 100 nF
  entre GPIO 32 y GND. El firmware ya descarta pulsos separados por menos de 50 ms.
- **Pines que no se deben usar:** GPIO 0, 5, 12 y 15 (definen el modo de arranque) y GPIO 6 a 11
  (memoria flash interna). GPIO 34 a 39 son solo de entrada y no tienen pull-up.

---

## Verificación al encender

Con el monitor serie (`pio device monitor`, 115200 baudios) se debe ver:

```text
[INFO] ATINA-FW:0.2.0;
[INFO] BME280: ok, DHT11: ok
```

Si aparece `no detectado`:
- **BME280:** revisar SDA y SCL (no invertidos), la alimentación y la dirección (SDO a GND = 0x76).
- **DHT11:** revisar el cable de datos en GPIO 25 y la resistencia de 10 kΩ.

**Comprobar la presión:** en Titicachi (~3100 m) debe rondar los **690 hPa**. Los datos del prototipo
mostraron una mediana de 861 hPa, que corresponde a unos 1300 m. Si la estación ya está instalada en
el sitio y sigue marcando un valor parecido, el sensor necesita calibración o reemplazo.

## Registro en el sistema

En **Dispositivos y sensores**, la estación debe tener registrados los sensores con estos códigos y
tipos. El firmware envía las lecturas con esos códigos:

| Código | Tipo de sensor | Modelo |
|---|---|---|
| `temp` | Temperatura del aire | BME280 (respaldo DHT11) |
| `hum` | Humedad relativa | BME280 (respaldo DHT11) |
| `pres` | Presión atmosférica | BME280 |
| `vol` | Volumen de agua captada | Pluviómetro de balancín |
| `nivel` | Nivel de almacenamiento | JSN-SR04T |
