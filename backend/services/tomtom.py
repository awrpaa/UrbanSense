import os
from typing import Any

import requests


FLOW_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
INCIDENTS_URL = "https://api.tomtom.com/traffic/services/5/incidentDetails"


def _key() -> str:
    key = os.getenv("TOMTOM_API_KEY", "").strip()
    if not key:
        raise RuntimeError("TOMTOM_API_KEY is not configured")
    return key


def congestion_from_speed(current_speed: float, free_flow_speed: float, confidence: float = 1.0) -> dict[str, Any]:
    if free_flow_speed <= 0:
        return {"score": None, "level": "UNKNOWN"}
    raw = max(0.0, min(100.0, (1.0 - current_speed / free_flow_speed) * 100.0))
    score = raw * max(0.0, min(1.0, confidence))
    level = "LOW" if score < 20 else "MEDIUM" if score < 50 else "HIGH"
    return {"score": round(score, 2), "level": level}


def flow_segment(latitude: float, longitude: float, timeout: float = 8.0) -> dict[str, Any]:
    response = requests.get(
        FLOW_URL,
        params={"key": _key(), "point": f"{latitude},{longitude}", "unit": "kmph"},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json().get("flowSegmentData", {})
    current = float(data.get("currentSpeed", 0) or 0)
    free_flow = float(data.get("freeFlowSpeed", 0) or 0)
    confidence = float(data.get("confidence", 1) or 1)
    return {
        "current_speed": current,
        "free_flow_speed": free_flow,
        "confidence": confidence,
        **congestion_from_speed(current, free_flow, confidence),
    }


def incident_details(bbox: str, timeout: float = 8.0) -> dict[str, Any]:
    """Return raw TomTom incident payload for a bounding box.

    Keep the API key server-side. The exact incident fields vary by incident type,
    so the dashboard should treat the returned payload as external-source data.
    """
    response = requests.get(
        INCIDENTS_URL,
        params={"key": _key(), "bbox": bbox, "fields": "{incidents{type,geometry,properties}}"},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    incidents = data.get("incidents", [])
    return {"count": len(incidents), "incidents": incidents}
