"""Tier 1 road-damage inference adapter.

Loads the trained YOLO road model from TIER1_MODEL_PATH and converts detections
into the shared UrbanSense event contract. Model weights are intentionally kept
outside Git.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any


def _model_path() -> str:
    path = os.getenv("TIER1_MODEL_PATH", "").strip()
    if not path:
        raise RuntimeError("TIER1_MODEL_PATH is not configured")
    return path


def _severity(confidence: float, area_ratio: float) -> str:
    score = 0.65 * confidence + 0.35 * min(area_ratio / 0.15, 1.0)
    if score >= 0.75:
        return "HIGH"
    if score >= 0.50:
        return "MEDIUM"
    return "LOW"


def _sinkhole_risk(detections: list[dict[str, Any]]) -> float:
    """Surface-indicator risk score; not underground sinkhole prediction."""
    if not detections:
        return 0.0
    potholes = [d for d in detections if d["class_name"].lower().startswith("pothole")]
    cracks = [d for d in detections if "crack" in d["class_name"].lower()]
    alligator = [d for d in detections if "alligator" in d["class_name"].lower()]
    pothole_signal = min(1.0, sum(d["confidence"] for d in potholes) / 2.0)
    crack_signal = min(1.0, sum(d["confidence"] for d in cracks) / 2.0)
    structural_signal = min(1.0, len(alligator) * 0.5 + len(potholes) * 0.2)
    return round(100 * (0.50 * pothole_signal + 0.25 * crack_signal + 0.25 * structural_signal), 2)


def detect(image: Any, *, latitude: float | None = None, longitude: float | None = None,
           timestamp: datetime | None = None, bus_id: str | None = None,
           camera_id: str | None = None) -> list[dict[str, Any]]:
    """Run YOLO11 road-damage inference on one image/frame."""
    from ultralytics import YOLO

    model = YOLO(_model_path())
    result = model.predict(
        source=image,
        conf=float(os.getenv("TIER1_CONF", "0.10")),
        iou=float(os.getenv("TIER1_IOU", "0.50")),
        imgsz=int(os.getenv("TIER1_IMGSZ", "1280")),
        device=os.getenv("TIER1_DEVICE", "0"),
        verbose=False,
    )[0]

    timestamp = timestamp or datetime.now(timezone.utc)
    names = result.names
    detections: list[dict[str, Any]] = []
    height, width = result.orig_shape
    frame_area = max(1, width * height)

    for box in result.boxes:
        cls_id = int(box.cls.item())
        confidence = float(box.conf.item())
        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
        area_ratio = max(0.0, (x2 - x1) * (y2 - y1) / frame_area)
        detections.append({
            "class_id": cls_id,
            "class_name": str(names[cls_id]),
            "confidence": confidence,
            "bbox": [round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)],
            "area_ratio": area_ratio,
        })

    events: list[dict[str, Any]] = []
    for index, det in enumerate(detections):
        events.append({
            "event_id": f"ROAD-{timestamp.strftime('%Y%m%d%H%M%S%f')}-{index}",
            "tier": 1,
            "event_type": "ROAD_DEFECT",
            "timestamp": timestamp,
            "location": {"latitude": latitude, "longitude": longitude} if latitude is not None and longitude is not None else None,
            "confidence": det["confidence"],
            "severity": _severity(det["confidence"], det["area_ratio"]),
            "source": "FLEET",
            "evidence": {},
            "metadata": {"defect_type": det["class_name"], "bbox": det["bbox"], "bus_id": bus_id, "camera_id": camera_id},
        })

    risk = _sinkhole_risk(detections)
    if risk > 0:
        events.append({
            "event_id": f"SINKHOLE-{timestamp.strftime('%Y%m%d%H%M%S%f')}",
            "tier": 1,
            "event_type": "SINKHOLE_RISK_ASSESSMENT",
            "timestamp": timestamp,
            "location": {"latitude": latitude, "longitude": longitude} if latitude is not None and longitude is not None else None,
            "confidence": None,
            "severity": "HIGH" if risk >= 70 else "MEDIUM" if risk >= 40 else "LOW",
            "source": "FLEET",
            "evidence": {},
            "metadata": {"risk_score": risk, "basis": "surface_visual_indicators", "bus_id": bus_id, "camera_id": camera_id},
        })
    return events
