#pragma once

#include <Arduino.h>

// Cola persistente de lecturas pendientes en LittleFS.
// Cada línea del archivo es una lectura en JSON; sobrevive a reinicios y cortes de energía.
namespace pending {

bool begin();
bool append(const String &readingJson);
// Lee hasta `maxItems` lecturas desde el inicio de la cola (sin eliminarlas).
size_t peek(String *out, size_t maxItems);
// Elimina las primeras `count` lecturas (tras confirmación del servidor).
bool drop(size_t count);
size_t size();

}  // namespace pending
