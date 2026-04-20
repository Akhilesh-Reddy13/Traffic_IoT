/*
 * ESP32-CAM — CameraWebServer for Traffic Density Controller
 * 
 * Based on the Arduino ESP32 CameraWebServer example.
 * Streams MJPEG at http://<IP>:81/stream
 *
 * WIRING (USB-TTL → ESP32-CAM):
 *   5V  → 5V
 *   GND → GND
 *   TX  → U0R
 *   RX  → U0T
 *   GND → IO0  (only during upload, remove after flashing)
 *
 * UPLOAD:
 *   1. Connect IO0 → GND
 *   2. Press RST on ESP32-CAM
 *   3. Upload from Arduino IDE (Board: AI Thinker ESP32-CAM)
 *   4. Remove IO0 → GND jumper
 *   5. Press RST again to run
 *   6. Open Serial Monitor at 115200 baud to see IP address
 */

#include "esp_camera.h"
#include <WiFi.h>

// ─── WiFi credentials (EDIT THESE) ─────────────────────────
const char* ssid     = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// ─── Camera model ───────────────────────────────────────────
#define CAMERA_MODEL_AI_THINKER
#include "camera_pins.h"

// Forward declaration for the streaming server
void startCameraServer();

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(true);
  Serial.println();

  // ── Camera configuration ──────────────────────────────────
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0       = Y2_GPIO_NUM;
  config.pin_d1       = Y3_GPIO_NUM;
  config.pin_d2       = Y4_GPIO_NUM;
  config.pin_d3       = Y5_GPIO_NUM;
  config.pin_d4       = Y6_GPIO_NUM;
  config.pin_d5       = Y7_GPIO_NUM;
  config.pin_d6       = Y8_GPIO_NUM;
  config.pin_d7       = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;

  // VGA resolution — best balance of quality & frame rate
  if (psramFound()) {
    config.frame_size   = FRAMESIZE_VGA;   // 640x480
    config.jpeg_quality = 12;              // 10-15 recommended
    config.fb_count     = 2;
  } else {
    config.frame_size   = FRAMESIZE_QVGA;  // 320x240 fallback
    config.jpeg_quality = 15;
    config.fb_count     = 1;
  }

  // ── Initialize camera ─────────────────────────────────────
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x\n", err);
    return;
  }
  Serial.println("Camera initialized successfully");

  // ── Connect to WiFi ───────────────────────────────────────
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.println("WiFi connected!");

  // ── Start streaming server ────────────────────────────────
  startCameraServer();

  Serial.println("─────────────────────────────────────");
  Serial.print("Stream URL: http://");
  Serial.print(WiFi.localIP());
  Serial.println(":81/stream");
  Serial.println("─────────────────────────────────────");
}

void loop() {
  delay(10000);  // Main loop idle — streaming handled by server task
}
