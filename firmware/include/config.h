#pragma once

#include <Arduino.h>

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

bool loadConfig(StationConfig &cfg);
void saveConfig(const StationConfig &cfg);
// Procesa comandos de configuración recibidos por el puerto serie. Devuelve true si cambió la configuración.
bool handleSerialConfig(StationConfig &cfg);

// Pines y constantes de hardware.
constexpr int PIN_RAIN_GAUGE = 27;       // pluviómetro de balancín / caudalímetro (pulsos)
constexpr float LITERS_PER_PULSE = 0.05; // calibrar según el colector
constexpr int PIN_LEVEL_TRIG = 25;       // sensor ultrasónico del tanque (JSN-SR04T)
constexpr int PIN_LEVEL_ECHO = 26;
constexpr float TANK_SENSOR_HEIGHT_CM = 200.0; // distancia del sensor al fondo del tanque
constexpr int PIN_FOG = 34;              // sensor óptico/analógico de niebla (opcional)

// Códigos de sensor registrados en el sistema para este dispositivo.
#define SENSOR_TEMP "temp"
#define SENSOR_HUM "hum"
#define SENSOR_PRESSURE "pres"
#define SENSOR_VOLUME "vol"
#define SENSOR_LEVEL "nivel"
#define SENSOR_FOG "niebla"

#define FIRMWARE_VERSION "0.1.0"
