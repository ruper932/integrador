// Sketch de prueba en banco (no se compila con el firmware): punto de acceso Wi-Fi propio,
// DHT + BME280 en GPIO 25 / 27 (SDA) / 26 (SCL) y registro en CSV. De aquí salió data/último paquete.csv.
// Para usarlo, cópielo como src/main.cpp en un proyecto aparte.
#include <Arduino.h>
#include <Wire.h>
#include <BME280I2C.h>
#include <DHT.h>
#include <WiFi.h>
#include <WebServer.h>
#include <SPIFFS.h>

// Configuración de pines
#define PIN_SDA 27
#define PIN_SCL 26
#define DHTPIN 25
#define DHTTYPE DHT22

// Configuración de la red Wi-Fi del ESP32
const char* ssid = "Estacion_Meteorologica";
const char* password = "CAMBIAR_ANTES_DE_COMPILAR"; // mínimo 8 caracteres; no versionar la clave real

BME280I2C bmp;
DHT dht(DHTPIN, DHTTYPE);
WebServer server(80);

// Nombre del archivo donde se guardará el historial en la flash interna
const char* logFile = "/datos_clima.csv";
unsigned long ultimoRegistro = 0;
const unsigned long intervaloRegistro = 10000; // Guardar datos cada 10 segundos (ajustable)

// Variables globales para el estado actual
float temp_bmp = NAN;
float pres_bmp = NAN;
float hum_dht = NAN;
bool status_bmp = false;
bool status_dht = false;

// Función para inicializar o verificar el BMP280 sin colgar el código
void verificarBMP() {
  status_bmp = bmp.begin();
  if (!status_bmp) {
    temp_bmp = NAN;
    pres_bmp = NAN;
  }
}

void handleRoot() {
  String html = "<!DOCTYPE html><html><head><meta charset='UTF-8'><meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "<title>Monitor Ambiental</title>";
  html += "<style>body{font-family:sans-serif;background:#f4f4f9;padding:20px;text-align:center;}";
  html += ".card{background:#fff;padding:20px;border-radius:10px;margin:15px auto;max-width:400px;box-shadow:0 4px 8px rgba(0,0,0,0.1);}";
  html += ".error{color:#e74c3c;font-weight:bold;} .ok{color:#2ecc71;}";
  html += ".btn{display:inline-block;padding:12px 24px;background:#3498db;color:#fff;text-decoration:none;border-radius:5px;margin-top:20px;font-weight:bold;}</style>";
  html += "<script>setInterval(() => { location.reload(); }, 3000);</script>"; // Recarga cada 3s
  html += "</head><body>";
  html += "<h2>Estación de Recopilación ESP32</h2>";

  // Panel BMP280
  html += "<div class='card'><h3>Sensor de Presión y Temperatura</h3>";
  if (status_bmp && !isnan(temp_bmp)) {
    html += "<p>Estado: <span class='ok'>CONECTADO</span></p>";
    html += "<p><b>Temperatura:</b> " + String(temp_bmp, 2) + " °C</p>";
    html += "<p><b>Presión:</b> " + String(pres_bmp, 2) + " hPa</p>";
  } else {
    html += "<p>Estado: <span class='error'>DESCONECTADO / ERROR</span></p>";
  }
  html += "</div>";

  // Panel DHT22
  html += "<div class='card'><h3>Sensor de Humedad</h3>";
  if (status_dht && !isnan(hum_dht)) {
    html += "<p>Estado: <span class='ok'>CONECTADO</span></p>";
    html += "<p><b>Humedad Relativa:</b> " + String(hum_dht, 2) + " %</p>";
  } else {
    html += "<p>Estado: <span class='error'>DESCONECTADO / ERROR</span></p>";
  }
  html += "</div>";

  // Opciones de descarga
  html += "<div class='card'><h3>Historial de Almacenamiento</h3>";
  html += "<a href='/descargar' class='btn' download>Descargar CSV a Celular</a><br><br>";
  html += "<a href='/borrar' class='btn' style='background:#e74c3c;' onclick=\"return confirm('¿Borrar todo el historial?');\">Borrar Historial</a>";
  html += "</div>";

  html += "</body></html>";
  server.send(200, "text/html", html);
}

void handleDownload() {
  if (SPIFFS.exists(logFile)) {
    File file = SPIFFS.open(logFile, "r");
    server.streamFile(file, "text/csv");
    file.close();
  } else {
    server.send(404, "text/plain", "No hay datos registrados aún.");
  }
}

void handleClear() {
  if (SPIFFS.exists(logFile)) {
    SPIFFS.remove(logFile);
  }
  server.send(200, "text/html", "<h3>Historial borrado.</h3><a href='/'>Volver</a>");
}

void setup() {
  Serial.begin(115200);

  // Inicializar almacenamiento interno SPIFFS
  if (!SPIFFS.begin(true)) {
    Serial.println("¡Error al inicializar SPIFFS! Los datos no se guardarán de forma permanente.");
  }

  // Inicializar bus I2C y primer intento del BMP
  Wire.begin(PIN_SDA, PIN_SCL);
  verificarBMP();

  // Inicializar DHT22
  dht.begin();
  status_dht = !isnan(dht.readHumidity());

  // Configurar ESP32 como Punto de Acceso (Access Point)
  WiFi.softAP(ssid, password);
  Serial.println("\n--- Red Wi-Fi Iniciada ---");
  Serial.print("Conéctate a: "); Serial.println(ssid);
  Serial.print("IP del ESP32: "); Serial.println(WiFi.softAPIP());

  // Configurar rutas del servidor web
  server.on("/", handleRoot);
  server.on("/descargar", handleDownload);
  server.on("/borrar", handleClear);
  server.begin();
}

void loop() {
  server.handleClient(); // Atender peticiones del celular

  // Leer y almacenar periódicamente de forma asíncrona
  if (millis() - ultimoRegistro >= intervaloRegistro) {
    ultimoRegistro = millis();

    // Intentar leer BMP280 de forma segura
    float dummy_hum = NAN;
    bmp.read(pres_bmp, temp_bmp, dummy_hum, BME280::TempUnit_Celsius, BME280::PresUnit_hPa);

    // Si la lectura da un valor imposible o falla, re-verificamos la conexión física
    if (isnan(temp_bmp) || temp_bmp < -40.0) {
      verificarBMP();
    }

    // Intentar leer DHT22 de forma segura
    hum_dht = dht.readHumidity();
    status_dht = !isnan(hum_dht);

    // Escribir los datos en el archivo log .csv dentro de la memoria flash
    File file = SPIFFS.open(logFile, "a"); // Modo 'a' añade datos al final del archivo
    if (file) {
      file.print(millis() / 1000); // Marca de tiempo relativa en segundos
      file.print(",");

      if (status_bmp && !isnan(temp_bmp)) file.print(String(temp_bmp, 2));
      else file.print("ERROR_BMP");
      file.print(",");

      if (status_bmp && !isnan(pres_bmp)) file.print(String(pres_bmp, 2));
      else file.print("ERROR_BMP");
      file.print(",");

      if (status_dht && !isnan(hum_dht)) file.print(String(hum_dht, 2));
      else file.print("ERROR_DHT");

      file.println();
      file.close();

      Serial.println("-> Datos guardados en memoria interna.");
    }
  }
}