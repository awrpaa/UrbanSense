"""Tier 3 MVA inference adapter.

Uses the trained YOLO11n five-class MVA model from MVA_py.ipynb:
0 Vehicle, 1 Rider, 2 Helmet, 3 No Helmet, 4 Licence Plate.
ByteTrack is used for temporal IDs and EasyOCR reads detected plates.
RTO lookup supports the project's mock PostgreSQL database and falls back
to an optional local SQLite database for Colab/demo testing.
"""
from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2


def _model_path() -> str:
    path = os.getenv("TIER3_MODEL_PATH", "").strip()
    if not path:
        raise RuntimeError("TIER3_MODEL_PATH is not configured")
    return path


def _clean_plate(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def _plate_variants(plate: str) -> list[str]:
    """Generate conservative Indian-plate formatting variants."""
    p = _clean_plate(plate)
    variants = [p]
    if len(p) >= 8:
        variants.append(p[:2] + p[2:4] + "-" + p[4:6] + "-" + p[6:])
    return list(dict.fromkeys(variants))


def _rto_lookup(plate: str) -> dict[str, Any]:
    """Look up a synthetic RTO record using DATABASE_URL when available.

    The SQL supplied for UrbanSense is a mock/synthetic RTO database. This
    function deliberately does not imply access to a live government system.
    """
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return {"found": False, "registration_number": plate}

    # PostgreSQL URL: postgresql://user:password@host:5432/dbname
    if database_url.startswith(("postgresql://", "postgres://")):
        try:
            import psycopg
            with psycopg.connect(database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT registration_number, owner_name, vehicle_make,
                               vehicle_model, rto_code, status
                        FROM vehicles
                        WHERE UPPER(REPLACE(registration_number, '-', '')) = %s
                        LIMIT 1
                        """,
                        (_clean_plate(plate),),
                    )
                    row = cur.fetchone()
            if row:
                return {
                    "found": True,
                    "registration_number": row[0],
                    "owner_name": row[1],
                    "vehicle_make": row[2],
                    "vehicle_model": row[3],
                    "rto_code": row[4],
                    "status": row[5],
                }
        except Exception as exc:
            return {"found": False, "registration_number": plate, "lookup_error": str(exc)}
        return {"found": False, "registration_number": plate}

    # SQLite is useful for local/Colab copies of the mock database.
    db_path = database_url.removeprefix("sqlite:///")
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute(
                "SELECT registration_number, owner_name, vehicle_make, vehicle_model, rto_code, status "
                "FROM vehicles WHERE UPPER(REPLACE(registration_number, '-', '')) = ? LIMIT 1",
                (_clean_plate(plate),),
            )
            row = cur.fetchone()
            conn.close()
            if row:
                return {
                    "found": True,
                    "registration_number": row[0],
                    "owner_name": row[1],
                    "vehicle_make": row[2],
                    "vehicle_model": row[3],
                    "rto_code": row[4],
                    "status": row[5],
                }
        except Exception as exc:
            return {"found": False, "registration_number": plate, "lookup_error": str(exc)}
    return {"found": False, "registration_number": plate}


def _get_reader():
    import easyocr
    return easyocr.Reader(
        [os.getenv("TIER3_OCR_LANG", "en")],
        gpu=os.getenv("TIER3_OCR_GPU", "true").lower() == "true",
    )


def detect_plate(image: Any) -> list[dict[str, Any]]:
    """Detect licence plates with the trained YOLO11 MVA model and OCR them."""
    from ultralytics import YOLO

    frame = image if hasattr(image, "shape") else cv2.imread(str(image))
    if frame is None:
        raise ValueError("Could not load input image")

    model = YOLO(_model_path())
    result = model.predict(
        source=frame,
        conf=float(os.getenv("TIER3_PLATE_CONF", "0.35")),
        imgsz=int(os.getenv("TIER3_IMGSZ", "800")),
        verbose=False,
    )[0]
    reader = _get_reader()
    candidates: list[dict[str, Any]] = []

    for box in result.boxes:
        if int(box.cls.item()) != 4:
            continue
        x1, y1, x2, y2 = [max(0, int(v)) for v in box.xyxy[0].tolist()]
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            continue
        for _, text, ocr_conf in reader.readtext(crop, detail=1, paragraph=False):
            plate = _clean_plate(text)
            if len(plate) >= 5:
                candidates.append({
                    "plate_number": plate,
                    "plate_confidence": round(float(ocr_conf), 4),
                    "detector_confidence": round(float(box.conf.item()), 4),
                    "bbox": [x1, y1, x2, y2],
                    "rto": _rto_lookup(plate),
                })
    return candidates


def create_violation_event(
    *,
    violation_type: str,
    image: Any,
    latitude: float | None = None,
    longitude: float | None = None,
    vehicle_id: str | None = None,
    timestamp: datetime | None = None,
    detection_confidence: float | None = None,
    bus_id: str | None = None,
    camera_id: str | None = None,
) -> list[dict[str, Any]]:
    """Emit enforcement-ready UrbanSense events from a violation frame."""
    timestamp = timestamp or datetime.now(timezone.utc)
    plates = detect_plate(image)
    events: list[dict[str, Any]] = []

    # Preserve a useful event even when OCR fails; enforcement remains reviewable.
    if not plates:
        plates = [{
            "plate_number": None,
            "plate_confidence": None,
            "detector_confidence": None,
            "bbox": None,
            "rto": {"found": False},
        }]

    for index, plate in enumerate(plates):
        confidence_parts = [
            x for x in (
                detection_confidence,
                plate.get("detector_confidence"),
                plate.get("plate_confidence"),
            ) if x is not None
        ]
        combined = sum(confidence_parts) / len(confidence_parts) if confidence_parts else None
        rto = plate.get("rto", {"found": False})
        events.append({
            "event_id": f"MVA-{timestamp.strftime('%Y%m%d%H%M%S%f')}-{index}",
            "tier": 3,
            "event_type": "TRAFFIC_VIOLATION",
            "timestamp": timestamp,
            "location": (
                {"latitude": latitude, "longitude": longitude}
                if latitude is not None and longitude is not None else None
            ),
            "confidence": combined,
            "severity": "HIGH" if combined is not None and combined >= 0.80 else "MEDIUM",
            "source": "FLEET",
            "evidence": {},
            "metadata": {
                "violation_type": violation_type,
                "vehicle_id": vehicle_id,
                "plate_number": plate.get("plate_number"),
                "plate_confidence": plate.get("plate_confidence"),
                "detection_confidence": detection_confidence,
                "rto_match": rto,
                "bus_id": bus_id,
                "camera_id": camera_id,
                "enforcement_status": "PENDING_REVIEW",
            },
        })
    return events


def track_and_detect(video_source: str, *, latitude: float | None = None,
                     longitude: float | None = None, bus_id: str | None = None,
                     camera_id: str | None = None) -> list[dict[str, Any]]:
    """Run the notebook's YOLO11 + ByteTrack MVA logic on a video.

    This focuses on the notebook's implemented NO_HELMET and WRONG_WAY checks.
    """
    from collections import defaultdict
    from ultralytics import YOLO

    model = YOLO(_model_path())
    reader = _get_reader()
    tracker = "bytetrack.yaml"
    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        raise ValueError(f"Could not open video source: {video_source}")

    trajectory_history: dict[int, list[tuple[int, int]]] = defaultdict(list)
    logged: set[tuple[int, str]] = set()
    events: list[dict[str, Any]] = []
    frame_idx = 0
    legal_direction_y = 1

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        result = model.track(
            frame, tracker=tracker, persist=True,
            conf=float(os.getenv("TIER3_CONF", "0.35")),
            imgsz=int(os.getenv("TIER3_IMGSZ", "800")), verbose=False,
        )[0]
        if result.boxes.id is None:
            continue

        boxes = result.boxes.xyxy.cpu().numpy()
        ids = result.boxes.id.int().cpu().numpy()
        classes = result.boxes.cls.int().cpu().numpy()
        confidences = result.boxes.conf.cpu().numpy()
        riders, helmets, no_helmets, plates = [], [], [], []

        for box, track_id, cls, conf in zip(boxes, ids, classes, confidences):
            entity = {"id": int(track_id), "box": box, "conf": float(conf)}
            if cls == 1: riders.append(entity)
            elif cls == 2: helmets.append(entity)
            elif cls == 3: no_helmets.append(entity)
            elif cls == 4: plates.append(entity)

        def iou(a, b):
            x1, y1 = max(a[0], b[0]), max(a[1], b[1])
            x2, y2 = min(a[2], b[2]), min(a[3], b[3])
            inter = max(0, x2-x1) * max(0, y2-y1)
            area_a = max(0, a[2]-a[0]) * max(0, a[3]-a[1])
            area_b = max(0, b[2]-b[0]) * max(0, b[3]-b[1])
            return inter / (area_a + area_b - inter + 1e-6)

        for rider in riders:
            rx1, ry1, rx2, ry2 = rider["box"]
            head = [rx1, ry1, rx2, ry1 + 0.35*(ry2-ry1)]
            no_helmet = any(iou(head, x["box"]) > 0.05 for x in no_helmets)
            helmet = any(iou(head, x["box"]) > 0.05 for x in helmets)
            if not (no_helmet or not helmet):
                continue
            key = (rider["id"], "NO_HELMET")
            if key in logged:
                continue
            logged.add(key)
            plate_candidates = []
            for plate in plates:
                if iou(rider["box"], plate["box"]) > 0:
                    x1, y1, x2, y2 = map(int, plate["box"])
                    crop = frame[max(0,y1):max(0,y2), max(0,x1):max(0,x2)]
                    if crop.size:
                        for _, text, ocr_conf in reader.readtext(crop, detail=1, paragraph=False):
                            cleaned = _clean_plate(text)
                            if len(cleaned) >= 5:
                                plate_candidates.append((cleaned, float(ocr_conf), float(plate["conf"])))
            if plate_candidates:
                plate_text, ocr_conf, plate_conf = max(plate_candidates, key=lambda x: x[1])
                rto = _rto_lookup(plate_text)
            else:
                plate_text, ocr_conf, plate_conf = None, None, None
                rto = {"found": False}
            events.append({
                "event_id": f"MVA-{bus_id or 'BUS'}-{frame_idx}-{rider['id']}",
                "tier": 3, "event_type": "TRAFFIC_VIOLATION",
                "timestamp": datetime.now(timezone.utc),
                "location": {"latitude": latitude, "longitude": longitude} if latitude is not None and longitude is not None else None,
                "confidence": rider["conf"], "severity": "HIGH",
                "source": "FLEET", "evidence": {},
                "metadata": {"violation_type": "NO_HELMET", "vehicle_id": rider["id"],
                              "plate_number": plate_text, "plate_confidence": ocr_conf,
                              "plate_detector_confidence": plate_conf, "rto_match": rto,
                              "frame_idx": frame_idx, "bus_id": bus_id, "camera_id": camera_id,
                              "enforcement_status": "PENDING_REVIEW"}
            })

        for entity in riders:
            cx = int((entity["box"][0]+entity["box"][2])/2)
            cy = int((entity["box"][1]+entity["box"][3])/2)
            trajectory_history[entity["id"]].append((cx, cy))
            if len(trajectory_history[entity["id"]]) >= 15:
                dy = trajectory_history[entity["id"]][-1][1] - trajectory_history[entity["id"]][-15][1]
                if dy * legal_direction_y < -25:
                    key = (entity["id"], "WRONG_WAY")
                    if key not in logged:
                        logged.add(key)
                        events.append({
                            "event_id": f"MVA-{bus_id or 'BUS'}-{frame_idx}-{entity['id']}-WRONG",
                            "tier": 3, "event_type": "TRAFFIC_VIOLATION",
                            "timestamp": datetime.now(timezone.utc),
                            "location": {"latitude": latitude, "longitude": longitude} if latitude is not None and longitude is not None else None,
                            "confidence": entity["conf"], "severity": "HIGH", "source": "FLEET", "evidence": {},
                            "metadata": {"violation_type": "WRONG_WAY", "vehicle_id": entity["id"],
                                          "frame_idx": frame_idx, "bus_id": bus_id, "camera_id": camera_id,
                                          "enforcement_status": "PENDING_REVIEW"}
                        })
    cap.release()
    return events
