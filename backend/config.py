"""
Configuration for Traffic Density Controller.
Override settings via environment variables or modify defaults here.
"""
import os

# ─── Video Source ───────────────────────────────────────────────
# ESP32-CAM stream URL or local video file path for testing
VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", "http://10.24.175.158:81/stream")

# ─── Model Settings ────────────────────────────────────────────
USE_GPU = os.getenv("USE_GPU", "false").lower() == "true"
MODEL_PATH = os.getenv("MODEL_PATH", "yolov8n.pt")
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.4"))

# COCO class IDs for vehicles
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

# ─── Traffic Controller ────────────────────────────────────────
MIN_GREEN_TIME = 10   # seconds
MAX_GREEN_TIME = 60   # seconds
YELLOW_TIME = 3       # seconds
ALL_RED_TIME = 2      # seconds
DENSITY_UPDATE_INTERVAL = 5  # how often to recalculate green times

# ─── Lane ROI Defaults (normalized 0-1 coordinates) ────────────
# Two lanes: left half = Direction A, right half = Direction B
DEFAULT_LANE_ROIS = {
    "lane_1": {
        "name": "Direction A",
        "polygon": [[0.0, 0.0], [0.48, 0.0], [0.48, 1.0], [0.0, 1.0]],
        "color": [72, 209, 204],  # medium turquoise
    },
    "lane_2": {
        "name": "Direction B",
        "polygon": [[0.52, 0.0], [1.0, 0.0], [1.0, 1.0], [0.52, 1.0]],
        "color": [255, 107, 53],  # coral orange
    },
}

# ─── Server ─────────────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 8000
