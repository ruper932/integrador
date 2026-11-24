// Estación IoT de monitoreo de atrapanieblas — ESP32.
//
// Ciclo:
//  1. Cada `sampleSeconds` toma lecturas y las guarda en la cola persistente (LittleFS).
//  2. Si hay conexión, envía la cola por lotes a la API local (HTTP/JSON) y elimina
//     solo lo que el servidor confirmó. Sin conexión, las lecturas se conservan y se
//     reenvían al restablecerse. Cada lectura lleva un message_id único (sin duplicados).
//  3. Variables no medidas (sensor ausente o fallido) se envían como null, nunca como 0.
//  4. El volumen se envía como valor INCREMENTAL: litros captados desde la lectura anterior.
//  5. La respuesta de cada lote trae el intervalo de muestreo elegido en el sistema web; si cambió, se
//     aplica desde el ciclo siguiente y se guarda en la memoria no volátil.
//  6. Tras cada muestreo (y como máximo una vez por hora) consulta si el sistema le asignó otra versión
//     de firmware; si es así la descarga, el cliente verifica el MD5, la instala y reinicia (OTA).

#include <ArduinoJson.h>
#include <BME280I2C.h>
#include <HTTPClient.h>
#include <HTTPUpdate.h>
#include <WiFi.h>
#include <Wire.h>
#include <time.h>

#include "buffer.h"
#include "config.h"
#include "dht_sensor.h"

#ifndef HAS_FOG_SENSOR
#define HAS_FOG_SENSOR 0
#endif

constexpr int PIN_STATUS_LED = 2;
constexpr size_t BATCH_SIZE = 50;
constexpr uint32_t COMM_LOSS_WARNING_MS = 30UL * 60UL * 1000UL;
constexpr uint32_t FIRMWARE_CHECK_MS = 60UL * 60UL * 1000UL;

// Marca que el servidor busca en el firmware.bin para conocer su versión (se imprime al arrancar,
// así el enlazador la conserva).
static const char FIRMWARE_MARKER[] = "ATINA-FW:" FIRMWARE_VERSION ";";

static StationConfig cfg;
static BME280I2C bme;  // dirección 0x76 (SDO a GND)
static bool hasBme = false;
static bool bmeHasHumidity = false;  // los módulos BMP280 vendidos como BME280 no miden humedad

static volatile uint32_t pulseCount = 0;
static volatile uint32_t lastPulseMs = 0;
static uint32_t lastSampleMs = 0;
static uint32_t lastSuccessMs = 0;
static uint32_t lastWifiAttemptMs = 0;
static uint32_t lastFirmwareCheckMs = 0;
static bool firmwareChecked = false;

void IRAM_ATTR onPulse() {
  uint32_t now = millis();
  if (now - lastPulseMs > 50) {  // antirrebote del balancín
    pulseCount++;
    lastPulseMs = now;
  }
}

static String uuid4() {
  uint8_t b[16];
  for (int i = 0; i < 16; i += 4) {
    uint32_t r = esp_random();
    memcpy(b + i, &r, 4);
  }
  b[6] = (b[6] & 0x0F) | 0x40;
  b[8] = (b[8] & 0x3F) | 0x80;
  char out[37];
  snprintf(out, sizeof(out), "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x", b[0], b[1], b[2],
           b[3], b[4], b[5], b[6], b[7], b[8], b[9], b[10], b[11], b[12], b[13], b[14], b[15]);
  return String(out);
}

static bool timeIsSynced() { return time(nullptr) > 1700000000; }

static String isoNowUtc() {
  time_t now = time(nullptr);
  struct tm t;
  gmtime_r(&now, &t);
  char buf[25];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &t);
  return String(buf);
}

static void queueReading(const char *sensorCode, float value, bool measured, const char *unit, const String &ts) {
  JsonDocument doc;
  doc["message_id"] = uuid4();
  doc["sensor_code"] = sensorCode;
  doc["measured_at"] = ts;
  if (measured && !isnan(value)) {
    doc["value"] = value;
  } else {
    doc["value"] = nullptr;
  }
  doc["unit"] = unit;
  String line;
  serializeJson(doc, line);
  if (!pending::append(line)) Serial.println("[ERROR] No se pudo guardar la lectura en la memoria local.");
}

static float readTankLevelCm() {
  digitalWrite(PIN_LEVEL_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_LEVEL_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_LEVEL_TRIG, LOW);
  unsigned long echo = pulseIn(PIN_LEVEL_ECHO, HIGH, 30000);
  if (echo == 0) return NAN;  // sin eco: lectura no disponible
  float distance = echo * 0.0343f / 2.0f;
  float level = TANK_SENSOR_HEIGHT_CM - distance;
  return level < 0 ? NAN : level;
}

// Comando `sensores` (consola serie): ayuda a revisar el cableado en el sitio.
void printSensorDiagnostics() {
  Serial.print("[DIAG] I2C (SDA 27, SCL 26), direcciones que responden:");
  int found = 0;
  for (uint8_t address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() == 0) {
      Serial.printf(" 0x%02X", address);
      found++;
    }
  }
  Serial.println(found ? "  (el BME280 debe ser 0x76 o 0x77)" : " ninguna: revise SDA, SCL, 3V3 y GND del BME280");
  pinMode(PIN_DHT, INPUT_PULLUP);
  delay(2);
  int idle = digitalRead(PIN_DHT);
  float t = NAN, h = NAN;
  bool ok = readDht(PIN_DHT, DHT_TYPE, t, h);
  Serial.printf("[DIAG] DHT (GPIO %d): línea en reposo %s; lectura %s", PIN_DHT, idle ? "ALTA (bien)" : "BAJA (DATA a GND o sensor sin alimentación)",
                ok ? "correcta" : "sin respuesta");
  if (ok) Serial.printf(": %.1f C, %.0f %%", t, h);
  Serial.println();
}

static void sample() {
  if (!timeIsSynced()) {
    // Sin hora válida no se registran lecturas; los pulsos de volumen se siguen acumulando.
    Serial.println("[AVISO] Hora no sincronizada; se pospone la lectura.");
    return;
  }
  String ts = isoNowUtc();

  // BME280 primero (más preciso y mide hasta 100 % de humedad); el DHT11 cubre si el BME280 falla.
  float bmeP = NAN, bmeT = NAN, bmeH = NAN;
  if (hasBme) bme.read(bmeP, bmeT, bmeH, BME280::TempUnit_Celsius, BME280::PresUnit_hPa);
  if (isnan(bmeT)) {
    hasBme = bme.begin();  // conexión floja o sensor reiniciado: se reintenta en el próximo ciclo
    bmeP = bmeH = NAN;
  }
  if (!bmeHasHumidity) bmeH = NAN;
  float dhtT = NAN, dhtH = NAN;
  readDht(PIN_DHT, DHT_TYPE, dhtT, dhtH);

  queueReading(SENSOR_TEMP, isnan(bmeT) ? dhtT : bmeT, true, "C", ts);
  queueReading(SENSOR_HUM, isnan(bmeH) ? dhtH : bmeH, true, "%", ts);
  queueReading(SENSOR_PRESSURE, bmeP, true, "hPa", ts);
  if (isnan(bmeT) || isnan(dhtH)) {
    Serial.printf("[AVISO] BME280: %s, DHT11: %s\n", isnan(bmeT) ? "sin lectura" : "ok", isnan(dhtH) ? "sin lectura" : "ok");
  }

  noInterrupts();
  uint32_t pulses = pulseCount;
  pulseCount = 0;
  interrupts();
  queueReading(SENSOR_VOLUME, pulses * LITERS_PER_PULSE, true, "L", ts);

  float level = readTankLevelCm();
  queueReading(SENSOR_LEVEL, level, !isnan(level), "cm", ts);

#if HAS_FOG_SENSOR
  float fog = analogRead(PIN_FOG) * 100.0f / 4095.0f;
  queueReading(SENSOR_FOG, fog, true, "%", ts);
#endif

  Serial.printf("[INFO] Lecturas guardadas. Pendientes de envío: %u\n", (unsigned)pending::size());
}

static void ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  // El primer intento es inmediato; luego, uno cada 30 s mientras no haya conexión.
  if (lastWifiAttemptMs != 0 && millis() - lastWifiAttemptMs < 30000) return;
  lastWifiAttemptMs = millis();
  Serial.println("[INFO] Conectando a WiFi…");
  WiFi.begin(cfg.wifiSsid.c_str(), cfg.wifiPassword.c_str());
}

// Aplica el intervalo de muestreo que el servidor indica en la respuesta del lote.
static void applySampleInterval(const String &response) {
  JsonDocument filter;
  filter["sample_interval_s"] = true;
  JsonDocument doc;
  if (deserializeJson(doc, response, DeserializationOption::Filter(filter)) != DeserializationError::Ok) return;
  uint32_t seconds = doc["sample_interval_s"] | 0u;
  if (seconds < MIN_SAMPLE_SECONDS || seconds > MAX_SAMPLE_SECONDS || seconds == cfg.sampleSeconds) return;
  cfg.sampleSeconds = seconds;
  saveConfig(cfg);
  Serial.printf("[INFO] Intervalo de muestreo actualizado por el servidor: %u s\n", (unsigned)seconds);
}

static bool sendPending() {
  if (WiFi.status() != WL_CONNECTED || pending::size() == 0) return false;

  static String lines[BATCH_SIZE];
  size_t n = pending::peek(lines, BATCH_SIZE);
  if (n == 0) return false;

  JsonDocument doc;
  doc["batch_id"] = uuid4();
  doc["sent_at"] = isoNowUtc();
  doc["firmware_version"] = FIRMWARE_VERSION;
  JsonArray readings = doc["readings"].to<JsonArray>();
  for (size_t i = 0; i < n; i++) {
    JsonDocument item;
    if (deserializeJson(item, lines[i]) == DeserializationError::Ok) readings.add(item);
  }
  String body;
  serializeJson(doc, body);

  HTTPClient http;
  http.setTimeout(15000);
  http.begin(cfg.apiUrl);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Id", cfg.deviceId);
  http.addHeader("X-Device-Key", cfg.deviceKey);
  int status = http.POST(body);
  String response = status == 200 ? http.getString() : String();
  http.end();

  if (status == 200) {
    applySampleInterval(response);
    // El servidor confirmó el lote (aceptadas, observadas, rechazadas o duplicadas): se eliminan de la cola.
    pending::drop(n);
    lastSuccessMs = millis();
    Serial.printf("[INFO] Lote enviado (%u lecturas). Pendientes: %u\n", (unsigned)n, (unsigned)pending::size());
    return true;
  }
  if (status == 422) {
    // Lote con estructura inválida: se descarta para no bloquear la cola indefinidamente.
    Serial.println("[ERROR] El servidor rechazó la estructura del lote; se descarta.");
    pending::drop(n);
    return false;
  }
  // 401/403 (credencial o dispositivo inactivo), 5xx o sin respuesta: se conservan y se reintenta.
  Serial.printf("[AVISO] Envío fallido (HTTP %d). Se reintentará.\n", status);
  return false;
}

// Actualización OTA desde la API local. 304: nada que instalar; 200: imagen nueva (se reinicia al terminar).
static void checkFirmware() {
  int cut = cfg.apiUrl.indexOf("/measurements/batch");
  if (cut < 0) {
    Serial.println("[AVISO] api_url no termina en /measurements/batch; no se consultan actualizaciones.");
    return;
  }
  HTTPClient http;
  http.setTimeout(30000);
  http.begin(cfg.apiUrl.substring(0, cut) + "/firmware");
  http.addHeader("X-Device-Id", cfg.deviceId);
  http.addHeader("X-Device-Key", cfg.deviceKey);
  Serial.println("[INFO] Consultando actualizaciones de firmware…");
  switch (httpUpdate.update(http, FIRMWARE_VERSION)) {
    case HTTP_UPDATE_NO_UPDATES:
      Serial.println("[INFO] Firmware al día.");
      break;
    case HTTP_UPDATE_OK:  // no se llega: el ESP32 se reinicia con la versión nueva
      break;
    case HTTP_UPDATE_FAILED:
      Serial.printf("[AVISO] Actualización fallida: %s. Se reintentará.\n", httpUpdate.getLastErrorString().c_str());
      break;
  }
}

static void reportCommunicationState() {
  bool lost = millis() - lastSuccessMs > COMM_LOSS_WARNING_MS;
  // LED encendido fijo: comunicación correcta. Parpadeo: sin comunicación con el servidor.
  digitalWrite(PIN_STATUS_LED, lost ? (millis() / 500) % 2 : HIGH);
  static uint32_t lastLog = 0;
  if (lost && millis() - lastLog > 60000) {
    lastLog = millis();
    Serial.printf("[AVISO] Sin comunicación con el servidor. Lecturas pendientes: %u\n", (unsigned)pending::size());
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);
  pinMode(PIN_STATUS_LED, OUTPUT);
  pinMode(PIN_LEVEL_TRIG, OUTPUT);
  pinMode(PIN_LEVEL_ECHO, INPUT);
  pinMode(PIN_RAIN_GAUGE, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_RAIN_GAUGE), onPulse, FALLING);

  if (!pending::begin()) Serial.println("[ERROR] No se pudo montar LittleFS.");

  while (!loadConfig(cfg)) {
    Serial.println("Configuración incompleta. Use: set <clave> <valor> y luego save. Escriba `show` para revisar.");
    uint32_t start = millis();
    while (millis() - start < 10000) {
      if (handleSerialConfig(cfg)) break;
      delay(50);
    }
  }

  Serial.printf("[INFO] %s\n", FIRMWARE_MARKER);
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL);
  hasBme = bme.begin();
  bmeHasHumidity = hasBme && bme.chipModel() == BME280::ChipModel_BME280;
  float probeT, probeH;
  delay(1000);  // el DHT11 necesita ~1 s tras encenderse
  bool hasDht = readDht(PIN_DHT, DHT_TYPE, probeT, probeH);
  Serial.printf("[INFO] BME280: %s, DHT11: %s\n",
                hasBme ? (bmeHasHumidity ? "ok" : "ok (BMP280, sin humedad)") : "no detectado",
                hasDht ? "ok" : "no detectado");

  WiFi.mode(WIFI_STA);
  ensureWifi();
  configTime(0, 0, cfg.ntpServer.c_str());  // NTP del servidor local; las fechas se envían en UTC
  lastSuccessMs = millis();
}

void loop() {
  handleSerialConfig(cfg);
  ensureWifi();

  bool sampled = false;
  if (millis() - lastSampleMs >= cfg.sampleSeconds * 1000UL || lastSampleMs == 0) {
    lastSampleMs = millis();
    sample();
    sampled = true;
  }
  // Vacía la cola en lotes sucesivos mientras haya conexión.
  while (sendPending()) {
    delay(100);
  }
  // Justo después de muestrear: si se reinicia por una actualización, solo se pierden los pulsos de
  // volumen de esos segundos (la cola pendiente está en LittleFS y sobrevive al reinicio).
  if (sampled && WiFi.status() == WL_CONNECTED &&
      (!firmwareChecked || millis() - lastFirmwareCheckMs >= FIRMWARE_CHECK_MS)) {
    firmwareChecked = true;
    lastFirmwareCheckMs = millis();
    checkFirmware();
  }
  reportCommunicationState();
  delay(200);
}
