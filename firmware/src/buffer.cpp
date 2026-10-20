#include "buffer.h"

#include <LittleFS.h>

namespace pending {

static const char *QUEUE = "/pending.jsonl";
static const char *TMP = "/pending.tmp";
// Límite para no llenar la memoria flash (~2 semanas a 5 min con 6 sensores).
static const size_t MAX_LINES = 25000;
static size_t lineCount = 0;

static size_t countLines() {
  File f = LittleFS.open(QUEUE, "r");
  if (!f) return 0;
  size_t n = 0;
  while (f.available()) {
    if (f.read() == '\n') n++;
  }
  f.close();
  return n;
}

bool begin() {
  if (!LittleFS.begin(true)) return false;
  lineCount = countLines();
  return true;
}

size_t size() { return lineCount; }

bool append(const String &readingJson) {
  if (lineCount >= MAX_LINES) drop(1);  // se descarta la lectura más antigua
  File f = LittleFS.open(QUEUE, "a");
  if (!f) return false;
  f.print(readingJson);
  f.print('\n');
  f.close();
  lineCount++;
  return true;
}

size_t peek(String *out, size_t maxItems) {
  File f = LittleFS.open(QUEUE, "r");
  if (!f) return 0;
  size_t n = 0;
  while (f.available() && n < maxItems) {
    String line = f.readStringUntil('\n');
    if (line.length()) out[n++] = line;
  }
  f.close();
  return n;
}

bool drop(size_t count) {
  File src = LittleFS.open(QUEUE, "r");
  if (!src) return false;
  File dst = LittleFS.open(TMP, "w");
  if (!dst) {
    src.close();
    return false;
  }
  size_t skipped = 0;
  size_t kept = 0;
  while (src.available()) {
    String line = src.readStringUntil('\n');
    if (!line.length()) continue;
    if (skipped < count) {
      skipped++;
      continue;
    }
    dst.print(line);
    dst.print('\n');
    kept++;
  }
  src.close();
  dst.close();
  LittleFS.remove(QUEUE);
  LittleFS.rename(TMP, QUEUE);
  lineCount = kept;
  return true;
}

}  // namespace pending
