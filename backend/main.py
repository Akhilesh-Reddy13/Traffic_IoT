"""
Traffic Density Controller — FastAPI Server
Captures video, runs YOLOv8n detection, manages traffic signals,
and streams results to the web dashboard via WebSocket.
"""
import asyncio
import base64
import json
import time
import threading
from pathlib import Path
from contextlib import asynccontextmanager

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional

import config
from stream.esp32_capture import VideoCapture
from detection.detector import VehicleDetector
from detection.tracker import CentroidTracker
from detection.lane_roi import LaneManager
from controller.traffic_controller import TrafficController


# ════════════════════════════════════════════════════════════════
#  Processing Pipeline (runs in background thread)
# ════════════════════════════════════════════════════════════════

class Pipeline:
    """Captures frames, detects vehicles, counts per lane, controls signals."""

    def __init__(self):
        self.capture = VideoCapture(config.VIDEO_SOURCE)
        self.detector = VehicleDetector(
            config.MODEL_PATH, config.CONFIDENCE_THRESHOLD, config.USE_GPU
        )
        self.tracker = CentroidTracker()
        self.lane_manager = LaneManager(config.DEFAULT_LANE_ROIS)
        self.controller = TrafficController(
            list(config.DEFAULT_LANE_ROIS.keys()),
            config.MIN_GREEN_TIME, config.MAX_GREEN_TIME,
            config.YELLOW_TIME, config.ALL_RED_TIME,
        )

        self.latest_state = None
        self.lock = threading.Lock()
        self.running = False
        self.fps = 0.0
        self.density_timer = 0.0

    def start(self):
        self.capture.start()
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()
        print("[Pipeline] Started")

    def stop(self):
        self.running = False
        self.capture.stop()

    def _classify(self, count):
        if count == 0:   return "empty"
        if count <= 3:   return "low"
        if count <= 7:   return "medium"
        if count <= 12:  return "high"
        return "critical"

    def _loop(self):
        frame_times = []
        self.density_timer = time.time()

        while self.running:
            frame = self.capture.get_frame()
            if frame is None:
                time.sleep(0.02)
                continue

            t0 = time.time()

            # 1. Detect
            detections = self.detector.detect(frame)

            # 2. Track
            self.tracker.update(detections)

            # 3. Count per lane
            h, w = frame.shape[:2]
            lane_counts = self.lane_manager.count_all(detections, w, h)

            # 4. Update green times periodically
            if time.time() - self.density_timer > config.DENSITY_UPDATE_INTERVAL:
                self.controller.update_green_times(lane_counts)
                self.density_timer = time.time()

            # 5. Tick signal controller
            signal_state = self.controller.tick()

            # 6. Annotate frame
            annotated = frame.copy()
            self.lane_manager.draw_all(annotated)
            for det in detections:
                x1, y1, x2, y2 = det["bbox"]
                clr = (0, 255, 120)
                cv2.rectangle(annotated, (x1, y1), (x2, y2), clr, 2)
                lbl = f'{det["class_name"]} {det["confidence"]}'
                cv2.putText(annotated, lbl, (x1, y1 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, clr, 1)

            # 7. Encode to base64 JPEG
            _, buf = cv2.imencode(".jpg", annotated,
                                  [cv2.IMWRITE_JPEG_QUALITY, 75])
            frame_b64 = base64.b64encode(buf).decode("utf-8")

            # 8. FPS calculation
            elapsed = time.time() - t0
            frame_times.append(elapsed)
            if len(frame_times) > 30:
                frame_times.pop(0)
            avg = sum(frame_times) / len(frame_times)
            self.fps = round(1.0 / avg, 1) if avg > 0 else 0

            # 9. Build state snapshot
            density = {lid: self._classify(c) for lid, c in lane_counts.items()}
            with self.lock:
                self.latest_state = {
                    "frame": frame_b64,
                    "total_vehicles": len(detections),
                    "lane_counts": lane_counts,
                    "signal_state": signal_state,
                    "density": density,
                    "fps": self.fps,
                }

            # Throttle to ~25 fps max
            sleep = max(0, 0.04 - elapsed)
            time.sleep(sleep)

    def get_state(self):
        with self.lock:
            return self.latest_state


# ════════════════════════════════════════════════════════════════
#  FastAPI Application
# ════════════════════════════════════════════════════════════════

pipeline = Pipeline()


@asynccontextmanager
async def lifespan(app):
    """Start pipeline on startup, stop on shutdown."""
    pipeline.start()
    yield
    pipeline.stop()


app = FastAPI(title="Traffic Density Controller", lifespan=lifespan)

# Serve dashboard static files
DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"


# ── REST endpoints ──────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse(DASHBOARD_DIR / "index.html")


@app.get("/style.css")
async def style():
    return FileResponse(DASHBOARD_DIR / "style.css", media_type="text/css")


@app.get("/app.js")
async def script():
    return FileResponse(DASHBOARD_DIR / "app.js", media_type="application/javascript")


@app.get("/api/status")
async def status():
    return {
        "connected": pipeline.capture.connected,
        "source": pipeline.capture.source,
        "fps": pipeline.fps,
        "use_gpu": config.USE_GPU,
    }


@app.get("/api/lanes")
async def get_lanes():
    return pipeline.lane_manager.get_config()


class ROIUpdate(BaseModel):
    lane_id: str
    polygon: list


@app.post("/api/lanes")
async def update_lane(data: ROIUpdate):
    pipeline.lane_manager.update_lane_roi(data.lane_id, data.polygon)
    return {"ok": True}


class SettingsUpdate(BaseModel):
    video_source: Optional[str] = None
    confidence: Optional[float] = None
    use_gpu: Optional[bool] = None


@app.post("/api/settings")
async def update_settings(data: SettingsUpdate):
    if data.video_source:
        config.VIDEO_SOURCE = data.video_source
        pipeline.capture.update_source(data.video_source)
    if data.confidence is not None:
        config.CONFIDENCE_THRESHOLD = data.confidence
        pipeline.detector.set_confidence(data.confidence)
    if data.use_gpu is not None:
        config.USE_GPU = data.use_gpu
        pipeline.detector.set_device(data.use_gpu)
    return {"ok": True}


# ── WebSocket ───────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    print("[WS] Client connected")
    try:
        while True:
            state = pipeline.get_state()
            if state:
                await ws.send_text(json.dumps(state))
            await asyncio.sleep(0.08)  # ~12 updates/sec to dashboard
    except WebSocketDisconnect:
        print("[WS] Client disconnected")
    except Exception as e:
        print(f"[WS] Error: {e}")


# ── Entry point ─────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
