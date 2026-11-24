#include "config.h"

#include <Preferences.h>

static Preferences prefs;

bool loadConfig(StationConfig &cfg) {
  prefs.begin("station", true);
  cfg.wifiSsid = prefs.getString("ssid", "");
  cfg.wifiPassword = prefs.getString("wifi_pass", "");
  cfg.apiUrl = prefs.getString("api_url", "");
  cfg.deviceId = prefs.getString("device_id", "");
  cfg.deviceKey = prefs.getString("device_key", "");
  cfg.ntpServer = prefs.getString("ntp", "");
  cfg.sampleSeconds = prefs.getUInt("sample_s", 300);
  prefs.end();
  return cfg.isComplete();
}

void saveConfig(const StationConfig &cfg) {
  prefs.begin("station", false);
  prefs.putString("ssid", cfg.wifiSsid);
  prefs.putString("wifi_pass", cfg.wifiPassword);
  prefs.putString("api_url", cfg.apiUrl);
  prefs.putString("device_id", cfg.deviceId);
  prefs.putString("device_key", cfg.deviceKey);
  prefs.putString("ntp", cfg.ntpServer);
  prefs.putUInt("sample_s", cfg.sampleSeconds);
  prefs.end();
}

// Comandos: `set <clave> <valor>`, `show`, `save`, `clear`.
// Claves: ssid, wifi_pass, api_url, device_id, device_key, ntp, sample_s.
bool handleSerialConfig(StationConfig &cfg) {
  if (!Serial.available()) return false;
  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.isEmpty()) return false;

  if (line == "sensores") {
    printSensorDiagnostics();
    return false;
  }
  if (line == "show") {
    Serial.printf("ssid=%s api_url=%s device_id=%s ntp=%s sample_s=%u device_key=%s\n", cfg.wifiSsid.c_str(),
                  cfg.apiUrl.c_str(), cfg.deviceId.c_str(), cfg.ntpServer.c_str(), cfg.sampleSeconds,
                  cfg.deviceKey.length() ? "(configurada)" : "(vacía)");  // la clave nunca se imprime
    return false;
  }
  if (line == "save") {
    saveConfig(cfg);
    Serial.println("Configuración guardada.");
    return true;
  }
  if (line == "clear") {
    prefs.begin("station", false);
    prefs.clear();
    prefs.end();
    cfg = StationConfig();
    Serial.println("Configuración borrada.");
    return true;
  }
  if (line.startsWith("set ")) {
    int space = line.indexOf(' ', 4);
    if (space < 0) {
      Serial.println("Uso: set <clave> <valor>");
      return false;
    }
    String key = line.substring(4, space);
    String value = line.substring(space + 1);
    if (key == "ssid") cfg.wifiSsid = value;
    else if (key == "wifi_pass") cfg.wifiPassword = value;
    else if (key == "api_url") cfg.apiUrl = value;
    else if (key == "device_id") cfg.deviceId = value;
    else if (key == "device_key") cfg.deviceKey = value;
    else if (key == "ntp") cfg.ntpServer = value;
    else if (key == "sample_s") cfg.sampleSeconds = constrain(value.toInt(), (long)MIN_SAMPLE_SECONDS, (long)MAX_SAMPLE_SECONDS);
    else {
      Serial.println("Clave desconocida.");
      return false;
    }
    Serial.printf("%s actualizado (escriba `save` para guardar).\n", key.c_str());
    return false;
  }
  Serial.println("Comandos: show | sensores | set <clave> <valor> | save | clear");
  return false;
}
