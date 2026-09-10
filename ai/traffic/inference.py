"""Tier 2 traffic inference using YOLO26 + BoT-SORT.

The application intentionally exposes one class, Vehicle. COCO vehicle
subclasses are used internally only to filter detections.
"""
from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

VEHICLE_CLASSES = [1, 2, 3, 5, 7]  # bicycle, car, motorcycle, bus, truck in COCO


def _model_path() -> str:
    return os.getenv("TIER2_MODEL_PATH", "yolo26s.pt").strip()


def _congestion(density: float, slow: float, occupancy: float, persistence: float) -> float:
    return 0.35 * density + 0.30 * slow + 0.20 * occupancy + 0.15 * persistence


def track_video(source: Any, *, latitude: float | None = None, longitude: float | None = None,
                timestamp: datetime | None = None, bus_id: str | None = None,
                camera_id: str | None = None) -> list[dict[str, Any]]:
    """Track vehicles and emit relative congestion events.

    No physical km/h is claimed: movement is measured in image pixels because
    a moving bus camera is not a calibrated speed sensor.
    """
    if source is None:
        raise ValueError("Tier 2 requires a video or image source")
    from ultralytics import YOLO

    model = YOLO(_model_path())
    stride = int(os.getenv("TIER2_VID_STRIDE", "5"))
    conf = float(os.getenv("TIER2_CONF", "0.30"))
    imgsz = int(os.getenv("TIER2_IMGSZ", "640"))
    timestamp = timestamp or datetime.now(timezone.utc)
    observations: list[dict[str, Any]] = []
    previous_centers: dict[int, tuple[float, float]] = {}
    track_counts: dict[int, int] = defaultdict(int)

    results = model.track(source=source, tracker=os.getenv("TIER2_TRACKER", "botsort.yaml"),
                          classes=VEHICLE_CLASSES, conf=conf, iou=0.50, imgsz=imgsz,
                          device=os.getenv("TIER2_DEVICE", "0"), vid_stride=stride,
                          stream=True, verbose=False)

    for frame_index, result in enumerate(results):
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            observations.append({"frame": frame_index, "vehicles": 0, "slow_ratio": 0.0,
                                 "occupancy": 0.0, "persistence": 0.0})
            continue

        ids = boxes.id.int().cpu().tolist() if boxes.id is not None else list(range(len(boxes)))
        centers = boxes.xywh.cpu().tolist()
        height, width = result.orig_shape
        speeds: list[float] = []
        occupied_cells: set[tuple[int, int]] = set()

        for track_id, (cx, cy, bw, bh) in zip(ids, centers):
            track_id = int(track_id)
            track_counts[track_id] += 1
            if track_id in previous_centers:
                px, py = previous_centers[track_id]
                speeds.append(((cx - px) ** 2 + (cy - py) ** 2) ** 0.5)
            previous_centers[track_id] = (cx, cy)
            if 0.25 * height <= cy <= 0.95 * height:
                gx = min(7, max(0, int(cx / width * 8)))
                gy = min(4, max(0, int((cy / height - 0.25) / 0.70 * 5)))
                occupied_cells.add((gx, gy))

        median_movement = sorted(speeds)[len(speeds) // 2] if speeds else 0.0
        slow_threshold = float(os.getenv("TIER2_SLOW_THRESHOLD_PX", "4.95"))
        slow_ratio = sum(s <= slow_threshold for s in speeds) / len(speeds) if speeds else 0.0
        occupancy = len(occupied_cells) / 40.0
        persistence = sum(c >= 10 for c in track_counts.values()) / max(1, len(track_counts))
        observations.append({"frame": frame_index, "vehicles": len(boxes),
                             "slow_ratio": slow_ratio, "occupancy": occupancy,
                             "persistence": persistence,
                             "median_relative_movement_px": median_movement})

    if not observations:
        return []

    max_density = max(o["vehicles"] for o in observations) or 1
    events: list[dict[str, Any]] = []
    for o in observations:
        density_score = o["vehicles"] / max_density
        score = _congestion(density_score, o["slow_ratio"], o["occupancy"], o["persistence"])
        level = "HIGH" if score >= 0.65 else "MEDIUM" if score >= 0.35 else "LOW"
        events.append({
            "event_id": f"TRAFFIC-{o['frame']:08d}", "tier": 2,
            "event_type": "TRAFFIC_CONGESTION", "timestamp": timestamp,
            "location": {"latitude": latitude, "longitude": longitude}
                        if latitude is not None and longitude is not None else None,
            "confidence": None, "severity": level, "source": "FLEET", "evidence": {},
            "metadata": {
                "bus_id": bus_id, "camera_id": camera_id, "vehicle_count": o["vehicles"],
                "density_score": round(density_score, 4), "slow_score": round(o["slow_ratio"], 4),
                "occupancy_score": round(o["occupancy"], 4), "persistence_score": round(o["persistence"], 4),
                "congestion_score": round(score, 4), "relative_movement_only": True,
            },
        })
    return events
