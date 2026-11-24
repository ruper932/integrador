#pragma once

// Lector propio del DHT11/DHT22, seguro para el ESP32.
// La biblioteca de Adafruit espera los pulsos con las interrupciones desactivadas y sin límite de
// tiempo real: con el sensor ausente o mal conectado, esa espera supera los ~300 ms del vigilante
// de interrupciones y el ESP32 se reinicia en bucle. Aquí cada espera tiene un límite de 150-250 µs
// (peor caso ≈ 13 ms con interrupciones desactivadas) y un fallo solo devuelve NAN.
// Detecta solo si el sensor responde en formato DHT11 o DHT22/AM2302.

#ifndef DHT11
#define DHT11 11
#endif
#ifndef DHT22
#define DHT22 22
#endif

// Lee temperatura (°C) y humedad (%). Devuelve false (y NAN en ambos) si el sensor no responde o
// la suma de verificación no coincide. Respeta el intervalo mínimo entre lecturas del sensor.
bool readDht(int pin, int type, float &temperature, float &humidity);
