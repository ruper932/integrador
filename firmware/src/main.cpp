// Estación IoT de monitoreo de atrapanieblas — ESP32.
//
// Ciclo:
//  1. Cada `sampleSeconds` toma lecturas y las guarda en la cola persistente (LittleFS).
//  2. Si hay conexión, envía la cola por lotes a la API local (HTTP/JSON) y elimina
//     solo lo que el servidor confirmó. Sin conexión, las lecturas se conservan y se
//     reenvían al restablecerse. Cada lectura lleva un message_id único (sin duplicados).
//  3. Variables no medidas (sensor ausente o fallido) se envían como null, nunca como 0.
//  4. El volumen se envía como valor INCREMENTAL: litros captados desde la lectura anterior.

#include <Adafruit_BMP280.h>
#include <Adafruit_SHT31.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <Wire.h>
#include <time.h>

#include "buffer.h"
#include "config.h"

#ifndef HAS_FOG_SENSOR
#define HAS_FOG_SENSOR 0
#endif

constexpr int PIN_STATUS_LED = 2;
constexpr size_t BATCH_SIZE = 50;
constexpr uint32_t COMM_LOSS_WARNING_MS = 30UL * 60UL * 1000UL;

static StationConfig cfg;
static Adafruit_SHT31 sht31;
static Adafruit_BMP280 bmp;
static bool hasSht31 = false;
static bool hasBmp = false;

static volatile uint32_t pulseCount = 0;
static volatile uint32_t lastPulseMs = 0;
static uint32_t lastSampleMs = 0;
static uint32_t lastSuccessMs = 0;
static uint32_t lastWifiAttemptMs = 0;

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

static void sample() {
  if (!timeIsSynced()) {
    // Sin hora válida no se registran lecturas; los pulsos de volumen se siguen acumulando.
    Serial.println("[AVISO] Hora no sincronizada; se pospone la lectura.");
    return;
  }
  String ts = isoNowUtc();

  float t = hasSht31 ? sht31.readTemperature() : NAN;
  float h = hasSht31 ? sht31.readHumidity() : NAN;
  queueReading(SENSOR_TEMP, t, hasSht31, "C", ts);
  queueReading(SENSOR_HUM, h, hasSht31, "%", ts);

  float p = hasBmp ? bmp.readPressure() / 100.0f : NAN;
  queueReading(SENSOR_PRESSURE, p, hasBmp, "hPa", ts);

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
  if (millis() - lastWifiAttemptMs < 30000) return;
  lastWifiAttemptMs = millis();
  Serial.println("[INFO] Conectando a WiFi…");
  WiFi.begin(cfg.wifiSsid.c_str(), cfg.wifiPassword.c_str());
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
  http.end();

  if (status == 200) {
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

  Wire.begin();
  hasSht31 = sht31.begin(0x44);
  hasBmp = bmp.begin(0x76);
  Serial.printf("[INFO] SHT31: %s, BMP280: %s\n", hasSht31 ? "ok" : "no detectado", hasBmp ? "ok" : "no detectado");

  WiFi.mode(WIFI_STA);
  ensureWifi();
  configTime(0, 0, cfg.ntpServer.c_str());  // NTP del servidor local; las fechas se envían en UTC
  lastSuccessMs = millis();
}

void loop() {
  handleSerialConfig(cfg);
  ensureWifi();

  if (millis() - lastSampleMs >= cfg.sampleSeconds * 1000UL || lastSampleMs == 0) {
    lastSampleMs = millis();
    sample();
  }
  // Vacía la cola en lotes sucesivos mientras haya conexión.
  while (sendPending()) {
    delay(100);
  }
  reportCommunicationState();
  delay(200);
}
