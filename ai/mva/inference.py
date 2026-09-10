"""Tier 3 enforcement adapter.

Pipeline: vehicle/violation detection -> plate detection -> OCR -> event.
The actual plate detector weights are deployment assets and are configured via
TIER3_PLATE_MODEL_PATH. OCR output is confidence-aware and should remain
protected by RBAC, encryption and audit logging in production.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any


def _plate_model_path() -> str:
    path = os.getenv("TIER3_PLATE_MODEL_PATH", "").strip()
    if not path:
        raise RuntimeError("TIER3_PLATE_MODEL_PATH is not configured")
    return path


def _clean_plate(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def detect_plate(image: Any) -> list[dict[str, Any]]:
    """Detect plates and OCR them. Returns candidate plate records."""
    from ultralytics import YOLO
    import cv2
    import easyocr

    detector = YOLO(_plate_model_path())
    result = detector.predict(source=image, conf=float(os.getenv("TIER3_PLATE_CONF", "0.35")), verbose=False)[0]
    reader = easyocr.Reader([os.getenv("TIER3_OCR_LANG", "en")], gpu=os.getenv("TIER3_OCR_GPU", "true").lower() == "true")
    frame = image if hasattr(image, "shape") else cv2.imread(str(image))
    if frame is None:
        raise ValueError("Could not load input image")

    candidates: list[dict[str, Any]] = []
    for box in result.boxes:
        x1, y1, x2, y2 = [max(0, int(v)) for v in box.xyxy[0].tolist()]
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            continue
        ocr = reader.readtext(crop, detail=1, paragraph=False)
        for _, text, ocr_conf in ocr:
            plate = _clean_plate(text)
            if len(plate) >= 5:
                candidates.append({
                    "plate_number": plate,
                    "plate_confidence": round(float(ocr_conf), 4),
                    "detector_confidence": round(float(box.conf.item()), 4),
                    "bbox": [x1, y1, x2, y2],
                })
    return candidates


def create_violation_event(*, violation_type: str, image: Any, latitude: float | None = None,
                           longitude: float | None = None, vehicle_id: str | None = None,
                           timestamp: datetime | None = None, detection_confidence: float | None = None,
                           bus_id: str | None = None, camera_id: str | None = None) -> list[dict[str, Any]]:
    """Attach OCR candidates to a violation and emit enforcement-ready events."""
    timestamp = timestamp or datetime.now(timezone.utc)
    plates = detect_plate(image)
    events = []
    for index, plate in enumerate(plates):
        confidence_parts = [x for x in (detection_confidence, plate["detector_confidence"], plate["plate_confidence"]) if x is not None]
        combined = sum(confidence_parts) / len(confidence_parts) if confidence_parts else None
        events.append({
            "event_id": f"MVA-{timestamp.strftime('%Y%m%d%H%M%S%f')}-{index}",
            "tier": 3,
            "event_type": "TRAFFIC_VIOLATION",
            "timestamp": timestamp,
            "location": {"latitude": latitude, "longitude": longitude} if latitude is not None and longitude is not None else None,
            "confidence": combined,
            "severity": "HIGH" if combined is not None and combined >= 0.80 else "MEDIUM",
            "source": "FLEET",
            "evidence": {},
            "metadata": {
                "violation_type": violation_type, "vehicle_id": vehicle_id,
                "plate_number": plate["plate_number"], "plate_confidence": plate["plate_confidence"],
                "detection_confidence": detection_confidence, "bus_id": bus_id, "camera_id": camera_id,
                "enforcement_status": "PENDING_REVIEW",
            },
        })
    return events
