"""
YOLOv8n vehicle detector — filters detections to vehicle classes only.
Supports CPU and GPU inference.
"""
from ultralytics import YOLO

# COCO dataset class IDs for vehicles
VEHICLE_CLASSES = {2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


class VehicleDetector:
    """Wraps YOLOv8n for vehicle-only detection."""

    def __init__(self, model_path="yolov8n.pt", confidence=0.4, use_gpu=False):
        self.model = YOLO(model_path)
        self.confidence = confidence
        self.device = "cuda:0" if use_gpu else "cpu"
        self.vehicle_class_ids = list(VEHICLE_CLASSES.keys())
        print(f"[Detector] Loaded {model_path} on {self.device}")

    def detect(self, frame):
        """
        Run detection on a single frame.
        Returns list of dicts: {bbox, confidence, class_id, class_name, center}
        """
        results = self.model(
            frame,
            conf=self.confidence,
            device=self.device,
            classes=self.vehicle_class_ids,
            verbose=False,
        )

        detections = []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])

                detections.append(
                    {
                        "bbox": [int(x1), int(y1), int(x2), int(y2)],
                        "confidence": round(conf, 2),
                        "class_id": cls_id,
                        "class_name": VEHICLE_CLASSES.get(cls_id, "unknown"),
                        "center": [int((x1 + x2) / 2), int((y1 + y2) / 2)],
                    }
                )

        return detections

    def set_confidence(self, value):
        self.confidence = max(0.1, min(1.0, value))

    def set_device(self, use_gpu):
        self.device = "cuda:0" if use_gpu else "cpu"
        print(f"[Detector] Switched to {self.device}")
