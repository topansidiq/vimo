#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>
#include <PubSubClient.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <MPU6050.h>
#include <ArduinoJson.h>

// ============================================================
// PIN DEFINITIONS
// ============================================================
#define PIN_SDA 21
#define PIN_SCL 22
#define PIN_BUTTON 4
#define PIN_LED 17
#define PIN_BUILTIN 2
#define PIN_BUZZER 16

// ============================================================
// CONSTANTS
// ============================================================
#define AP_SSID "VIMO-CONFIG"
#define BUTTON_HOLD_MS 3000
#define SENSOR_INTERVAL 75

// ============================================================
// OBJECTS
// ============================================================
WebServer server(80);
Preferences prefs;
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
MPU6050 mpu;

// ============================================================
// CONFIG STRUCT
// ============================================================
struct Config
{
  String wifiSSID;
  String wifiPass;
  String mqttBroker;
  String mqttTopic;
  String mqttPanicTopic;
  String deviceName;
  String deviceLocation;
  String serverURL;
  bool configured = false;
};

Config cfg;

// ============================================================
// STATE
// ============================================================
bool apMode = false;
bool systemReady = false;
unsigned long lastSensorSend = 0;
unsigned long buttonPressTime = 0;
bool buttonHeld = false;
bool shouldReboot = false;
unsigned long rebootTimer = 0;
unsigned long lastMqttReconnect = 0;
bool buttonReleasedOnce = false;

// ============================================================
// BUZZER FUNCTIONS
// ============================================================
void beep(int count, int duration)
{
  for (int i = 0; i < count; i++)
  {
    digitalWrite(PIN_BUZZER, HIGH);
    delay(duration);
    digitalWrite(PIN_BUZZER, LOW);
    if (i < count - 1)
      delay(150);
  }
}

void beepBoot() { beep(1, 1500); }
void beepReady() { beep(2, 400); }
void beepPanic()
{
  for (int i = 0; i < 5; i++)
  {
    digitalWrite(PIN_BUZZER, HIGH);
    digitalWrite(PIN_LED, HIGH);
    delay(300);
    digitalWrite(PIN_BUZZER, LOW);
    digitalWrite(PIN_LED, LOW);
    delay(150);
  }
}
void beepReset() { beep(1, 1500); }

// ============================================================
// PREFERENCES (MEMORY)
// ============================================================
void saveConfig()
{
  prefs.begin("vimo", false);
  prefs.putString("wifiSSID", cfg.wifiSSID);
  prefs.putString("wifiPass", cfg.wifiPass);
  prefs.putString("mqttBroker", cfg.mqttBroker);
  prefs.putString("mqttTopic", cfg.mqttTopic);
  prefs.putString("mqttPanicTopic", cfg.mqttPanicTopic);
  prefs.putString("devName", cfg.deviceName);
  prefs.putString("devLocation", cfg.deviceLocation);
  prefs.putString("serverURL", cfg.serverURL);
  prefs.putBool("configured", true);
  prefs.end();
}

void loadConfig()
{
  prefs.begin("vimo", true);
  cfg.wifiSSID = prefs.getString("wifiSSID", "");
  cfg.wifiPass = prefs.getString("wifiPass", "");
  cfg.mqttBroker = prefs.getString("mqttBroker", "");
  cfg.mqttTopic = prefs.getString("mqttTopic", "");
  cfg.mqttPanicTopic = prefs.getString("mqttPanicTopic", "vimo/panic");
  cfg.deviceName = prefs.getString("devName", "");
  cfg.deviceLocation = prefs.getString("devLocation", "");
  cfg.serverURL = prefs.getString("serverURL", "");
  cfg.configured = prefs.getBool("configured", false);
  prefs.end();

  Serial.println("====== LOADED CONFIG ======");
  Serial.println("WiFi: " + (cfg.wifiSSID != "" ? cfg.wifiSSID : "Not Set"));
  Serial.println("MQTT Broker: " + (cfg.mqttBroker != "" ? cfg.mqttBroker : "Not Set"));
  Serial.println("MQT Topic: " + (cfg.mqttTopic != "" ? cfg.mqttTopic : "Not Set"));
  Serial.println("Device ID: " + (cfg.deviceName != "" ? cfg.deviceName : "Not Set"));
  Serial.println("Server URL: " + (cfg.serverURL != "" ? cfg.serverURL : "Not Set"));
  Serial.println("===========================");
}

void clearConfig()
{
  prefs.begin("vimo", false);
  prefs.clear();
  prefs.end();
}

// ============================================================
// HTML HELPER
// ============================================================
const char *HTML_STYLE = R"(
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'Courier New',monospace;background:#0a0a0a;color:#e0e0e0;padding:20px}
  h1{color:#00ff88;font-size:1.4em;margin-bottom:8px}
  h2{color:#00ccff;font-size:1.1em;margin:16px 0 8px}
  p,li{font-size:0.9em;line-height:1.6;color:#aaa}
  a{color:#00ff88;text-decoration:none}
  a:hover{text-decoration:underline}
  ul{padding-left:20px}
  form{margin-top:10px}
  input{width:100%;padding:8px;margin:6px 0 12px;background:#1a1a1a;border:1px solid #333;color:#e0e0e0;border-radius:4px;font-family:inherit}
  input:focus{outline:none;border-color:#00ff88}
  button{padding:10px 20px;background:#00ff88;color:#000;border:none;border-radius:4px;cursor:pointer;font-weight:bold;font-family:inherit}
  button:hover{background:#00cc66}
  .card{background:#111;border:1px solid #222;border-radius:8px;padding:16px;margin:10px 0}
  .badge{display:inline-block;padding:2px 8px;border-radius:12px;font-size:0.75em;background:#1a3a1a;color:#00ff88;border:1px solid #00ff88}
  .warn{color:#ffaa00}
  .nav{margin-bottom:20px;font-size:0.85em}
  .nav a{margin-right:12px}
</style>
)";

String htmlWrap(String title, String body)
{
  return "<!DOCTYPE html><html><head><meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>" + title + " - VIMO</title>" + String(HTML_STYLE) + "</head><body><div class='nav'><a href='/'>Home</a><a href='/help'>Help</a><a href='/health'>Health</a><a href='/about'>About</a><a href='/config'>Config</a><a href='/reset'>Reset</a></div>" + body + "</body></html>";
}

// ============================================================
// ENDPOINT HANDLERS
// ============================================================

// GET /
void handleRoot()
{
  String html = "<div class='card'><h1>Selamat Datang di VIMO</h1><p>Sistem monitoring getaran berbasis ESP32 + MPU6050.</p><p style='margin-top:8px'>Akses <a href='/help'>/help</a> untuk daftar endpoint.</p></div>";
  server.send(200, "text/html", htmlWrap("Home", html));
}

// GET /help
void handleHelp()
{
  String html = "<h1>Endpoint Guide</h1>";
  html += "<div class='card'><ul>";
  html += "<li><a href='/'>/</a> - Halaman selamat datang</li>";
  html += "<li><a href='/help'>/help</a> - Daftar endpoint ini</li>";
  html += "<li><a href='/health'>/health</a> - Status device (GET)</li>";
  html += "<li><a href='/about'>/about</a> - Metadata device & aplikasi (GET)</li>";
  html += "<li><a href='/config'>/config</a> - Form konfigurasi WiFi/MQTT/Server (GET & POST)</li>";
  html += "<li><a href='/reset'>/reset</a> - Reset ke setelan awal (GET untuk konfirmasi, POST untuk eksekusi)</li>";
  html += "</ul></div>";
  html += "<div class='card'><h2>POST /config/wifi</h2><p>Body: ssid, password</p></div>";
  html += "<div class='card'><h2>POST /config/mqtt</h2><p>Body: broker, topic, panic_topic</p></div>";
  html += "<div class='card'><h2>POST /config/server</h2><p>Body: name, location, url</p></div>";
  html += "<div class='card'><h2>POST /config/save</h2><p>Simpan semua config dan reboot</p></div>";
  server.send(200, "text/html", htmlWrap("Help", html));
}

// GET /health
void handleHealth()
{
  int16_t ax, ay, az, gx, gy, gz;
  mpu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);
  float temp = mpu.getTemperature() / 340.0 + 36.53;

  DynamicJsonDocument doc(512);
  doc["status"] = "ok";
  doc["mpu6050"] = mpu.testConnection() ? "connected" : "error";
  doc["wifi_config"] = cfg.wifiSSID != "" ? cfg.wifiSSID : "not set";
  doc["mqtt_config"] = cfg.mqttBroker != "" ? cfg.mqttBroker : "not set";
  doc["server_config"] = cfg.serverURL != "" ? cfg.serverURL : "not set";
  doc["configured"] = cfg.configured;
  doc["uptime_ms"] = millis();
  doc["temp_c"] = temp;

  String json;
  serializeJsonPretty(doc, json);
  server.send(200, "application/json", json);
}

// GET /about
void handleAbout()
{
  DynamicJsonDocument doc(512);
  doc["app"] = "VIMO";
  doc["version"] = "1.0.0";
  doc["chip"] = ESP.getChipModel();
  doc["chip_revision"] = ESP.getChipRevision();
  doc["flash_size"] = ESP.getFlashChipSize();
  doc["free_heap"] = ESP.getFreeHeap();
  doc["mac"] = WiFi.macAddress();
  doc["device_name"] = cfg.deviceName;
  doc["device_location"] = cfg.deviceLocation;
  doc["mqtt_broker"] = cfg.mqttBroker;
  doc["mqtt_topic"] = cfg.mqttTopic;
  doc["server_url"] = cfg.serverURL;
  doc["ap_ssid"] = AP_SSID;

  String json;
  serializeJsonPretty(doc, json);
  server.send(200, "application/json", json);
}

// GET /config
void handleConfigGet()
{
  String html = "<h1>Konfigurasi VIMO</h1>";

  // WiFi
  html += "<div class='card'><h2>WiFi</h2><form action='/config/wifi' method='POST'>";
  html += "<label>SSID</label><input name='ssid' value='" + cfg.wifiSSID + "'>";
  html += "<label>Password</label><input name='password' type='password'>";
  html += "<button type='submit'>Simpan WiFi</button></form></div>";

  // MQTT
  html += "<div class='card'><h2>MQTT</h2><form action='/config/mqtt' method='POST'>";
  html += "<label>Broker (IP/Host)</label><input name='broker' value='" + cfg.mqttBroker + "'>";
  html += "<label>Topic Sensor</label><input name='topic' value='" + cfg.mqttTopic + "'>";
  html += "<label>Topic Panic (subscribe)</label><input name='panic_topic' value='" + cfg.mqttPanicTopic + "'>";
  html += "<button type='submit'>Simpan MQTT</button></form></div>";

  // Server
  html += "<div class='card'><h2>Server</h2><form action='/config/server' method='POST'>";
  html += "<label>Nama Device</label><input name='name' value='" + cfg.deviceName + "'>";
  html += "<label>Lokasi</label><input name='location' value='" + cfg.deviceLocation + "'>";
  html += "<label>URL Server (HTTP POST)</label><input name='url' value='" + cfg.serverURL + "'>";
  html += "<button type='submit'>Simpan Server</button></form></div>";

  // Save & Reboot
  html += "<div class='card'><h2>Finalisasi</h2><p class='warn'>Setelah semua diisi, klik tombol di bawah untuk menyimpan dan reboot.</p>";
  html += "<form action='/config/save' method='POST' style='margin-top:10px'><button type='submit'>Simpan Semua & Reboot</button></form></div>";

  server.send(200, "text/html", htmlWrap("Config", html));
}

void handleConfigWifi()
{
  if (server.hasArg("ssid"))
    cfg.wifiSSID = server.arg("ssid");
  if (server.hasArg("password"))
    cfg.wifiPass = server.arg("password");
  server.sendHeader("Location", "/config");
  server.send(302);
}

void handleConfigMqtt()
{
  if (server.hasArg("broker"))
    cfg.mqttBroker = server.arg("broker");
  if (server.hasArg("topic"))
    cfg.mqttTopic = server.arg("topic");
  if (server.hasArg("panic_topic"))
    cfg.mqttPanicTopic = server.arg("panic_topic");
  server.sendHeader("Location", "/config");
  server.send(302);
}

void handleConfigServer()
{
  if (server.hasArg("name"))
    cfg.deviceName = server.arg("name");
  if (server.hasArg("location"))
    cfg.deviceLocation = server.arg("location");
  if (server.hasArg("url"))
    cfg.serverURL = server.arg("url");

  server.sendHeader("Location", "/config");
  server.send(302);
}

void handleConfigSave()
{
  saveConfig();
  String html = "<div class='card'><h1>Config Tersimpan</h1><p>Device akan reboot dalam 3 detik...</p></div>";
  html += "<script>setTimeout(()=>{window.location.href='/'},3000)</script>";
  server.send(200, "text/html", htmlWrap("Saved", html));
  shouldReboot = true;
  rebootTimer = millis();
}

// GET /reset
void handleResetGet()
{
  String html = "<div class='card'><h1>Reset Device</h1>";
  html += "<p class='warn'>Ini akan menghapus seluruh konfigurasi (WiFi, MQTT, Server) dan reboot ke mode AP.</p>";
  html += "<form action='/reset' method='POST' style='margin-top:12px'><button type='submit' style='background:#ff4444;color:#fff'>Konfirmasi Reset</button></form></div>";
  server.send(200, "text/html", htmlWrap("Reset", html));
}

void handleResetPost()
{
  clearConfig();
  String html = "<div class='card'><h1>Reset Berhasil</h1><p>Device akan reboot dalam 3 detik...</p></div>";
  server.send(200, "text/html", htmlWrap("Reset", html));
  delay(500);
  beepReset();
  delay(2500);
  ESP.restart();
}

// ============================================================
// MQTT
// ============================================================
void mqttCallback(char *topic, byte *payload, unsigned int length)
{
  String msg;
  for (unsigned int i = 0; i < length; i++)
    msg += (char)payload[i];

  if (String(topic) == cfg.mqttPanicTopic && msg == "panic")
  {
    beepPanic();
  }
}

bool mqttConnect()
{
  if (cfg.mqttBroker == "")
  {
    Serial.println("MQTT Broker is missing. Skipping MQTT connection...");
    return false;
  }
  mqttClient.setServer(cfg.mqttBroker.c_str(), 1883);
  mqttClient.setCallback(mqttCallback);

  String clientId = "VIMO-" + WiFi.macAddress();
  Serial.print("Connecting to MQTT: ");
  Serial.print(cfg.mqttBroker);

  if (mqttClient.connect(clientId.c_str()))
  {
    Serial.println(" -> SUCCESS");
    mqttClient.subscribe(cfg.mqttPanicTopic.c_str());
    return true;
  }
  Serial.println(" -> FAILED");
  return false;
}

void sendSensorData()
{
  if (!mqttClient.connected())
  {
    Serial.println("Warning: Sensor data not sent because MQTT is not connected.");
    return;
  }

  int16_t ax, ay, az, gx, gy, gz;
  mpu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);
  float temp = mpu.getTemperature() / 340.0 + 36.53;

  DynamicJsonDocument doc(256);
  char chipId[17];
  sprintf(chipId, "%llX", ESP.getEfuseMac());
  doc["deviceId"] = chipId; // Use ESP chip ID as device ID
  doc["accelX"] = ax;
  doc["accelY"] = ay;
  doc["accelZ"] = az;
  doc["gyroX"] = gx;
  doc["gyroY"] = gy;
  doc["gyroZ"] = gz;
  doc["temp"] = temp; // Keep temperature mapping

  String payload;
  serializeJson(doc, payload);
  mqttClient.publish(cfg.mqttTopic.c_str(), payload.c_str());

  Serial.println("PUBLISH topic (" + cfg.mqttTopic + "): " + payload);
}

// ============================================================
// BUTTON HANDLER
// ============================================================
void handleButton()
{
  int state = digitalRead(PIN_BUTTON);

  if (state == HIGH)
  {
    buttonReleasedOnce = true;
    buttonHeld = false;
  }
  else if (state == LOW && buttonReleasedOnce)
  {
    if (!buttonHeld)
    {
      buttonPressTime = millis();
      buttonHeld = true;
    }
    else if (millis() - buttonPressTime >= BUTTON_HOLD_MS)
    {
      // Reset
      digitalWrite(PIN_BUILTIN, LOW);
      clearConfig();
      beepReset();
      delay(500);
      ESP.restart();
    }
  }
}

// ============================================================
// SETUP AP MODE
// ============================================================
void startAP()
{
  digitalWrite(PIN_BUILTIN, LOW);
  Serial.println("Starting AP Mode...");
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID);
  apMode = true;
  Serial.print("Access Point Ready. SSID: ");
  Serial.println(AP_SSID);
  Serial.print("IP Address: ");
  Serial.println(WiFi.softAPIP());

  server.on("/", HTTP_GET, handleRoot);
  server.on("/help", HTTP_GET, handleHelp);
  server.on("/health", HTTP_GET, handleHealth);
  server.on("/about", HTTP_GET, handleAbout);
  server.on("/config", HTTP_GET, handleConfigGet);
  server.on("/config/wifi", HTTP_POST, handleConfigWifi);
  server.on("/config/mqtt", HTTP_POST, handleConfigMqtt);
  server.on("/config/server", HTTP_POST, handleConfigServer);
  server.on("/config/save", HTTP_POST, handleConfigSave);
  server.on("/reset", HTTP_GET, handleResetGet);
  server.on("/reset", HTTP_POST, handleResetPost);
  server.begin();
}

// ============================================================
// SETUP
// ============================================================
void setup()
{
  Serial.begin(115200);

  pinMode(PIN_BUTTON, INPUT_PULLUP);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_BUILTIN, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  digitalWrite(PIN_LED, LOW);
  digitalWrite(PIN_BUILTIN, LOW);
  digitalWrite(PIN_BUZZER, LOW);

  Wire.begin(PIN_SDA, PIN_SCL);
  mpu.initialize();

  loadConfig();
  beepBoot();

  if (cfg.configured && cfg.wifiSSID != "")
  {
    // Connect ke WiFi
    Serial.print("Connecting to WiFi: ");
    Serial.println(cfg.wifiSSID);

    WiFi.mode(WIFI_STA);
    WiFi.begin(cfg.wifiSSID.c_str(), cfg.wifiPass.c_str());

    int attempt = 0;
    while (WiFi.status() != WL_CONNECTED && attempt < 20)
    {
      delay(500);
      Serial.print(".");
      attempt++;
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED)
    {
      Serial.print("WiFi Connected! IP: ");
      Serial.println(WiFi.localIP());

      mqttConnect();
      systemReady = true;
      digitalWrite(PIN_BUILTIN, HIGH);
      beepReady();

      // POST device ke server jika ada
      if (cfg.serverURL != "")
      {
        Serial.print("Registering device to Server HTTP POST: ");
        Serial.println(cfg.serverURL);

        HTTPClient http;
        http.begin(cfg.serverURL.c_str());
        http.addHeader("Content-Type", "application/json");
        DynamicJsonDocument doc(256);
        char chipId[17];
        sprintf(chipId, "%llX", ESP.getEfuseMac());
        doc["id"] = chipId;
        doc["name"] = cfg.deviceName;
        doc["location"] = cfg.deviceLocation;
        String body;
        serializeJson(doc, body);
        int httpResponseCode = http.POST(body);
        Serial.print("HTTP Response code: ");
        Serial.println(httpResponseCode);
        http.end();
      }
    }
    else
    {
      // Gagal connect, fallback ke AP
      startAP();
    }
  }
  else
  {
    startAP();
  }
}

// ============================================================
// LOOP
// ============================================================
void loop()
{
  handleButton();

  if (shouldReboot)
  {
    if (millis() - rebootTimer >= 3000)
    {
      ESP.restart();
    }
  }

  if (apMode)
  {
    server.handleClient();
  }
  else
  {
    if (millis() - lastSensorSend >= SENSOR_INTERVAL)
    {
      lastSensorSend = millis();
      if (cfg.mqttBroker != "")
      {
        sendSensorData();
      }
      else
      {
        Serial.println("Reading sensors (Simulation only - MQTT Not Set)");
        int16_t ax, ay, az, gx, gy, gz;
        mpu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);
      }
    }

    if (cfg.mqttBroker != "")
    {
      if (mqttClient.connected())
      {
        mqttClient.loop();
      }
      else
      {
        if (millis() - lastMqttReconnect >= 5000)
        {
          lastMqttReconnect = millis();
          mqttConnect();
        }
      }
    }
  }
}