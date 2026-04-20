# 🚦 Traffic Density Controller

Real-time vehicle detection and adaptive traffic signal control using **ESP32-CAM** + **YOLOv8n** + a premium web dashboard.

## Architecture

```
ESP32-CAM (MJPEG stream) → Python Backend (YOLOv8n detection) → Web Dashboard (WebSocket)
```

## Quick Start (Testing with Video File)

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Add a Test Video

Place a traffic video file (e.g., `test_video.mp4`) in the `backend/` directory.

### 3. Configure Video Source

Edit `backend/config.py`:
```python
VIDEO_SOURCE = "test_video.mp4"        # Local file
# VIDEO_SOURCE = "http://192.168.1.100:81/stream"  # ESP32-CAM
USE_GPU = True   # Set False for CPU-only
```

Or use environment variables:
```bash
set VIDEO_SOURCE=test_video.mp4
set USE_GPU=true
```

### 4. Run the Server

```bash
cd backend
python main.py
```

### 5. Open Dashboard

Navigate to **http://localhost:8000** in your browser.

---

## ESP32-CAM Setup

### Wiring (USB-TTL → ESP32-CAM)

| USB-TTL | ESP32-CAM |
|---------|-----------|
| 5V      | 5V        |
| GND     | GND       |
| TX      | U0R       |
| RX      | U0T       |
| GND     | IO0 *(flash only)* |

### Flash Firmware

1. Open `firmware/esp32cam_firmware.ino` in Arduino IDE
2. Edit WiFi SSID and password
3. Board: **AI Thinker ESP32-CAM** (install ESP32 board package first)
4. Connect IO0→GND, press RST, upload
5. Remove IO0 jumper, press RST
6. Check Serial Monitor (115200 baud) for stream URL

---

## Project Structure

```
iot-tarffic/
├── backend/
│   ├── main.py                 # FastAPI server
│   ├── config.py               # Configuration
│   ├── requirements.txt
│   ├── stream/
│   │   └── esp32_capture.py    # Video capture module
│   ├── detection/
│   │   ├── detector.py         # YOLOv8n wrapper
│   │   ├── tracker.py          # Centroid tracker
│   │   └── lane_roi.py         # Lane ROI management
│   └── controller/
│       └── traffic_controller.py   # Signal timing algorithm
├── dashboard/
│   ├── index.html              # Web UI
│   ├── style.css               # Dark theme
│   └── app.js                  # WebSocket client
├── firmware/
│   └── esp32cam_firmware.ino   # ESP32-CAM sketch
└── README.md
```

## Algorithm

Green time for each lane is allocated **proportionally** to its vehicle count:

```
Gᵢ = clamp(G_min, G_max, (Vᵢ / V_total) × G_available)
```

- **G_min** = 10s, **G_max** = 60s
- Cycle length scales dynamically with total density
- Yellow = 3s, All-red clearance = 2s per phase
