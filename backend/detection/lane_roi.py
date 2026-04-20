"""
Lane ROI management — defines polygonal regions for each traffic lane
and counts vehicles whose centers fall within each region.
"""
import cv2
import numpy as np


class LaneROI:
    """A single lane region defined by a normalized polygon."""

    def __init__(self, lane_id, name, polygon, color):
        """
        Args:
            lane_id: Unique identifier string
            name: Human-readable name (e.g. "Direction A")
            polygon: List of [x, y] in normalized coords (0-1)
            color: BGR color tuple for visualization
        """
        self.lane_id = lane_id
        self.name = name
        self.polygon_normalized = np.array(polygon, dtype=np.float32)
        self.color = tuple(color)
        self.vehicle_count = 0
        self.vehicles = []

    def get_pixel_polygon(self, w, h):
        """Convert normalized polygon to pixel coordinates."""
        poly = self.polygon_normalized.copy()
        poly[:, 0] *= w
        poly[:, 1] *= h
        return poly.astype(np.int32)

    def count_vehicles(self, detections, w, h):
        """Count detections whose center is inside this ROI."""
        poly = self.get_pixel_polygon(w, h)
        self.vehicles = []

        for det in detections:
            cx, cy = det["center"]
            if cv2.pointPolygonTest(poly, (float(cx), float(cy)), False) >= 0:
                self.vehicles.append(det)

        self.vehicle_count = len(self.vehicles)
        return self.vehicle_count

    def draw(self, frame):
        """Draw semi-transparent ROI overlay with label on frame."""
        h, w = frame.shape[:2]
        poly = self.get_pixel_polygon(w, h)

        # Semi-transparent fill
        overlay = frame.copy()
        cv2.fillPoly(overlay, [poly], self.color)
        cv2.addWeighted(overlay, 0.15, frame, 0.85, 0, frame)

        # Border
        cv2.polylines(frame, [poly], True, self.color, 2)

        # Label at centroid
        cx, cy = poly.mean(axis=0).astype(int)
        label = f"{self.name}: {self.vehicle_count}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.rectangle(frame, (cx - 5, cy - th - 10), (cx + tw + 5, cy + 5), (0, 0, 0), -1)
        cv2.putText(frame, label, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.color, 2)
        return frame

    def update_polygon(self, polygon):
        self.polygon_normalized = np.array(polygon, dtype=np.float32)


class LaneManager:
    """Manages multiple lane ROIs."""

    def __init__(self, lane_configs):
        self.lanes = {}
        for lane_id, cfg in lane_configs.items():
            self.lanes[lane_id] = LaneROI(
                lane_id=lane_id,
                name=cfg["name"],
                polygon=cfg["polygon"],
                color=cfg["color"],
            )

    def count_all(self, detections, w, h):
        """Count vehicles in every lane. Returns {lane_id: count}."""
        counts = {}
        for lane_id, lane in self.lanes.items():
            counts[lane_id] = lane.count_vehicles(detections, w, h)
        return counts

    def draw_all(self, frame):
        """Draw all lane ROIs on the frame."""
        for lane in self.lanes.values():
            lane.draw(frame)
        return frame

    def update_lane_roi(self, lane_id, polygon):
        if lane_id in self.lanes:
            self.lanes[lane_id].update_polygon(polygon)

    def get_config(self):
        """Return current lane configuration as a serializable dict."""
        cfg = {}
        for lid, lane in self.lanes.items():
            cfg[lid] = {
                "name": lane.name,
                "polygon": lane.polygon_normalized.tolist(),
                "color": list(lane.color),
            }
        return cfg
