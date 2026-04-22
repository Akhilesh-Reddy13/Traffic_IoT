/*
 * app_httpd.cpp — MJPEG streaming HTTP server for ESP32-CAM
 *
 * Provides startCameraServer() which launches an HTTP server on port 81
 * with a /stream endpoint that serves an MJPEG stream.
 *
 * Based on the official Espressif CameraWebServer example.
 */

#include "Arduino.h"
#include "esp_camera.h"
#include "esp_http_server.h"
#include "esp_timer.h"


// MJPEG stream boundary
#define PART_BOUNDARY "123456789000000000000987654321"
static const char *_STREAM_CONTENT_TYPE =
    "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char *_STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char *_STREAM_PART =
    "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

httpd_handle_t stream_httpd = NULL;

// ─── MJPEG stream handler ───────────────────────────────────────
static esp_err_t stream_handler(httpd_req_t *req) {
  camera_fb_t *fb = NULL;
  esp_err_t res = ESP_OK;
  char part_buf[64];

  res = httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);
  if (res != ESP_OK) {
    return res;
  }

  // Allow cross-origin access so the web dashboard can embed the stream
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

  while (true) {
    fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Camera capture failed");
      res = ESP_FAIL;
    } else {
      // Send boundary
      if (res == ESP_OK) {
        size_t hlen = snprintf(part_buf, 64, _STREAM_PART, fb->len);
        res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY,
                                    strlen(_STREAM_BOUNDARY));
        if (res == ESP_OK) {
          res = httpd_resp_send_chunk(req, part_buf, hlen);
        }
        if (res == ESP_OK) {
          res = httpd_resp_send_chunk(req, (const char *)fb->buf, fb->len);
        }
      }
    }

    if (fb) {
      esp_camera_fb_return(fb);
      fb = NULL;
    }

    if (res != ESP_OK) {
      break;
    }
  }

  return res;
}

// ─── Single JPEG capture handler (/capture) ─────────────────────
static esp_err_t capture_handler(httpd_req_t *req) {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Camera capture failed");
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }

  httpd_resp_set_type(req, "image/jpeg");
  httpd_resp_set_hdr(req, "Content-Disposition",
                     "inline; filename=capture.jpg");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

  esp_err_t res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
  esp_camera_fb_return(fb);
  return res;
}

// ─── Start the camera streaming server on port 81 ───────────────
void startCameraServer() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 81;

  // URI: /stream  →  MJPEG stream
  httpd_uri_t stream_uri = {.uri = "/stream",
                            .method = HTTP_GET,
                            .handler = stream_handler,
                            .user_ctx = NULL};

  // URI: /capture →  single JPEG frame
  httpd_uri_t capture_uri = {.uri = "/capture",
                             .method = HTTP_GET,
                             .handler = capture_handler,
                             .user_ctx = NULL};

  Serial.printf("Starting stream server on port %d\n", config.server_port);

  if (httpd_start(&stream_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(stream_httpd, &stream_uri);
    httpd_register_uri_handler(stream_httpd, &capture_uri);
    Serial.println("Stream server started successfully");
  } else {
    Serial.println("Error starting stream server!");
  }
}