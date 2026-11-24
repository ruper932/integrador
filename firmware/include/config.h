#pragma once

#include <Arduino.h>

#include "dht_sensor.h"  // DHT11 / DHT22

// Configuración de la estación guardada en NVS (Preferences).
// Se carga por puerto serie con el comando `config` (ver README.md); nunca se escribe en el código fuente.
struct StationConfig {
  String wifiSsid;
  String wifiPassword;
  String apiUrl;      // p. ej. http://192.168.1.10/api/v1/iot/measurements/batch
  String deviceId;    // identificador registrado en el sistema (X-Device-Id)
  String deviceKey;   // API key entregada al registrar el dispositivo (X-Device-Key)
  String ntpServer;   // servidor NTP de la red local (el servidor institucional)
  uint32_t sampleSeconds = 300;

  bool isComplete() const {
    return wifiSsid.length() && apiUrl.length() && deviceId.length() && deviceKey.length() && ntpServer.length();
  }
};

// Límites del intervalo de muestreo. El sistema web lo fija en 5 («tiempo real»), 30 o 60 s y lo envía
// en la respuesta de cada lote; por el puerto serie se acepta cualquier valor dentro de estos límites.
constexpr uint32_t MIN_SAMPLE_SECONDS = 5;
constexpr uint32_t MAX_SAMPLE_SECONDS = 3600;

bool loadConfig(StationConfig &cfg);
void saveConfig(const StationConfig &cfg);
// Procesa comandos de configuración recibidos por el puerto serie. Devuelve true si cambió la configuración.
bool handleSerialConfig(StationConfig &cfg);
// Comando `sensores`: estado del bus I2C y del DHT para revisar el cableado (definido en main.cpp).
void printSensorDiagnostics();

// Pines y constantes de hardware (conexiones en docs/conexiones_sensores_esp32.md).
// Estación meteorológica: BME280 (I²C) y DHT11; mismos pines que el prototipo probado en banco.
constexpr int PIN_I2C_SDA = 27;          // BME280 SDA
constexpr int PIN_I2C_SCL = 26;          // BME280 SCL
constexpr int PIN_DHT = 25;              // DHT11 DATA (resistencia de 10 kΩ a 3,3 V)
#ifndef DHT_TYPE
#define DHT_TYPE DHT11                   // tipo que se prueba primero; el lector detecta DHT11 o DHT22
#endif
constexpr int PIN_RAIN_GAUGE = 32;       // pluviómetro de balancín / caudalímetro (pulsos)
constexpr float LITERS_PER_PULSE = 0.05; // calibrar según el colector
constexpr int PIN_LEVEL_TRIG = 18;       // sensor ultrasónico del tanque (JSN-SR04T)
constexpr int PIN_LEVEL_ECHO = 19;       // ECO de 5 V: con divisor de tensión a 3,3 V
constexpr float TANK_SENSOR_HEIGHT_CM = 200.0; // distancia del sensor al fondo del tanque
constexpr int PIN_FOG = 34;              // sensor óptico/analógico de niebla (opcional)

// Códigos de sensor registrados en el sistema para este dispositivo.
#define SENSOR_TEMP "temp"
#define SENSOR_HUM "hum"
#define SENSOR_PRESSURE "pres"
#define SENSOR_VOLUME "vol"
#define SENSOR_LEVEL "nivel"
#define SENSOR_FOG "niebla"

// Aumentarla en cada versión que se cargue al sistema: el servidor la lee del firmware.bin y el ESP32
// solo instala una versión distinta de la que ejecuta.
#define FIRMWARE_VERSION "0.3.4"
