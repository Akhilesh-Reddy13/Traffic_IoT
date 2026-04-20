"""
Video capture module — supports ESP32-CAM MJPEG streams and local video files.
"""
import cv2
import numpy as np
import requests
import threading
import time


class VideoCapture:
    """Thread-safe frame grabber for ESP32-CAM streams or local video files."""

    def __init__(self, source):
        self.source = source
        self.frame = None
        self.lock = threading.Lock()
        self.running = False
        self.thread = None
        self.is_stream = isinstance(source, str) and source.startswith("http")
        self.fps = 30
        self.frame_count = 0
        self.connected = False

    def start(self):
        self.running = True
        if self.is_stream:
            self.thread = threading.Thread(target=self._capture_stream, daemon=True)
        else:
            self.thread = threading.Thread(target=self._capture_video, daemon=True)
        self.thread.start()
        print(f"[VideoCapture] Started — source: {self.source}")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=3)
        print("[VideoCapture] Stopped")

    def get_frame(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def _capture_stream(self):
        """Capture frames from ESP32-CAM MJPEG stream over HTTP."""
        while self.running:
            try:
                response = requests.get(self.source, stream=True, timeout=10)
                self.connected = True
                print(f"[VideoCapture] Connected to stream: {self.source}")
                img_bytes = bytes()

                for chunk in response.iter_content(chunk_size=1024):
                    if not self.running:
                        break
                    img_bytes += chunk
                    # Find JPEG start-of-image and end-of-image markers
                    a = img_bytes.find(b"\xff\xd8")
                    b = img_bytes.find(b"\xff\xd9")
                    if a != -1 and b != -1:
                        jpg = img_bytes[a : b + 2]
                        img_bytes = img_bytes[b + 2 :]
                        frame = cv2.imdecode(
                            np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR
                        )
                        if frame is not None:
                            with self.lock:
                                self.frame = frame
                                self.frame_count += 1

            except Exception as e:
                self.connected = False
                print(f"[VideoCapture] Stream error: {e}. Reconnecting in 2s...")
                time.sleep(2)

    def _capture_video(self):
        """Capture frames from a local video file (loops automatically)."""
        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            print(f"[VideoCapture] ERROR: Cannot open video: {self.source}")
            return

        self.fps = cap.get(cv2.CAP_PROP_FPS) or 30
        self.connected = True
        delay = 1.0 / self.fps
        print(f"[VideoCapture] Opened video at {self.fps:.1f} FPS")

        while self.running:
            ret, frame = cap.read()
            if not ret:
                # Loop back to start
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            with self.lock:
                self.frame = frame
                self.frame_count += 1

            time.sleep(delay)

        cap.release()

    def update_source(self, new_source):
        """Change video source at runtime."""
        self.stop()
        self.source = new_source
        self.is_stream = isinstance(new_source, str) and new_source.startswith("http")
        self.frame = None
        self.frame_count = 0
        self.connected = False
        self.start()
