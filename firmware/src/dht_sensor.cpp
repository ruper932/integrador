#include "dht_sensor.h"

#include <Arduino.h>
#include <math.h>

namespace {

constexpr uint32_t MIN_INTERVAL_MS = 2000;  // el DHT11 necesita ≥ 1 s entre lecturas
constexpr uint32_t RESPONSE_TIMEOUT_US = 250;  // el sensor contesta entre 20 y 200 µs después del inicio
constexpr uint32_t EDGE_TIMEOUT_US = 150;      // los pulsos del protocolo duran ~50-80 µs

uint32_t lastReadMs = 0;
bool hasLast = false;
bool lastOk = false;
float lastT = NAN, lastH = NAN;

// Espera mientras la línea esté en `level`; devuelve los µs transcurridos o -1 si vence el límite.
int32_t waitWhile(int pin, int level, uint32_t timeoutUs = EDGE_TIMEOUT_US) {
  uint32_t start = micros();
  while (digitalRead(pin) == level) {
    if (micros() - start > timeoutUs) return -1;
  }
  return static_cast<int32_t>(micros() - start);
}

// Señal de inicio en bajo: ~1 ms para el DHT22/AM2302 y ≥ 18 ms para el DHT11.
bool readFrame(int pin, uint32_t startLowUs, uint8_t data[5]) {
  pinMode(pin, INPUT_PULLUP);
  delay(2);
  pinMode(pin, OUTPUT);
  digitalWrite(pin, LOW);
  if (startLowUs >= 2000) delay(startLowUs / 1000);
  else delayMicroseconds(startLowUs);
  pinMode(pin, INPUT_PULLUP);

  bool ok = true;
  noInterrupts();
  // Respuesta del sensor: ~20-40 µs en alto, 80 µs en bajo y 80 µs en alto.
  if (waitWhile(pin, HIGH, RESPONSE_TIMEOUT_US) < 0 || waitWhile(pin, LOW) < 0 || waitWhile(pin, HIGH) < 0) ok = false;
  // 40 bits: cada uno empieza con ~50 µs en bajo; el alto dura ~26 µs (0) o ~70 µs (1).
  for (int i = 0; ok && i < 40; i++) {
    if (waitWhile(pin, LOW) < 0) {
      ok = false;
      break;
    }
    int32_t high = waitWhile(pin, HIGH);
    if (high < 0) {
      ok = false;
      break;
    }
    data[i / 8] = (data[i / 8] << 1) | (high > 40 ? 1 : 0);
  }
  interrupts();
  return ok && static_cast<uint8_t>(data[0] + data[1] + data[2] + data[3]) == data[4];
}

}  // namespace

bool readDht(int pin, int type, float &temperature, float &humidity) {
  if (hasLast && millis() - lastReadMs < MIN_INTERVAL_MS) {
    temperature = lastT;
    humidity = lastH;
    return lastOk;
  }
  // Se prueba primero la señal de inicio del tipo configurado y, si no hay respuesta, la del otro.
  uint8_t data[5] = {0, 0, 0, 0, 0};
  int order[2] = {type, type == DHT22 ? DHT11 : DHT22};
  lastOk = false;
  for (int candidate : order) {
    for (auto &b : data) b = 0;
    if (readFrame(pin, candidate == DHT22 ? 1100 : 20000, data)) {
      lastOk = true;
      break;
    }
    delay(50);
  }
  lastReadMs = millis();
  hasLast = true;
  lastT = lastH = NAN;
  if (lastOk) {
    // El formato se reconoce por el contenido (muchos módulos vendidos como «DHT11» son DHT22/AM2302 y
    // aceptan ambas señales): en el DHT22 el byte alto de la humedad vale 0-3 (≤ 100,0 %); el DHT11 mide
    // desde 20 % y ese byte es la humedad entera.
    if (data[0] <= 3) {
      lastH = ((data[0] << 8) | data[1]) * 0.1f;
      lastT = (((data[2] & 0x7F) << 8) | data[3]) * 0.1f;
      if (data[2] & 0x80) lastT = -lastT;
    } else {
      lastH = data[0] + data[1] * 0.1f;
      lastT = data[2] + (data[3] & 0x0F) * 0.1f;
      if (data[3] & 0x80) lastT = -lastT;
    }
    if (lastH < 0 || lastH > 100 || lastT < -40 || lastT > 80) {
      lastOk = false;
      lastT = lastH = NAN;
    }
  }
  temperature = lastT;
  humidity = lastH;
  return lastOk;
}
