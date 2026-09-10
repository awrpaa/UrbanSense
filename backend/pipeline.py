from datetime import datetime, timezone
import os
from typing import Any, Optional

from backend.schemas.events import UrbanSenseEvent


class UrbanSensePipeline:
    """Orchestrate Tier 1/2/3 adapters behind one shared event contract."""

    def __init__(self, tier1=None, tier2=None, tier3=None) -> None:
        self.adapters = {1: tier1, 2: tier2, 3: tier3}

    def process(self, *, image: Any = None, source: Any = None,
                latitude: Optional[float] = None, longitude: Optional[float] = None,
                timestamp: Optional[datetime] = None, bus_id: Optional[str] = None,
                camera_id: Optional[str] = None, tiers: Optional[list[int]] = None) -> list[UrbanSenseEvent]:
        timestamp = timestamp or datetime.now(timezone.utc)
        selected = tiers or [1, 2, 3]
        events: list[UrbanSenseEvent] = []
        context = {"image": image, "source": source, "latitude": latitude,
                   "longitude": longitude, "timestamp": timestamp,
                   "bus_id": bus_id, "camera_id": camera_id}
        for tier in selected:
            adapter = self.adapters.get(tier)
            if adapter is None:
                continue
            for event in adapter(**context):
                events.append(event if isinstance(event, UrbanSenseEvent)
                              else UrbanSenseEvent.model_validate(event))
        return events


def _tier1_adapter(**kwargs):
    from ai.road_damage.inference import detect
    image = kwargs.get("image")
    if image is None:
        raise ValueError("Tier 1 requires an image/frame")
    return detect(image=image, latitude=kwargs.get("latitude"), longitude=kwargs.get("longitude"),
                  timestamp=kwargs.get("timestamp"), bus_id=kwargs.get("bus_id"),
                  camera_id=kwargs.get("camera_id"))


def _tier2_adapter(**kwargs):
    from ai.traffic.inference import track_video
    source = kwargs.get("source") or kwargs.get("image")
    return track_video(source, latitude=kwargs.get("latitude"), longitude=kwargs.get("longitude"),
                       timestamp=kwargs.get("timestamp"), bus_id=kwargs.get("bus_id"),
                       camera_id=kwargs.get("camera_id"))


def _tier3_adapter(**kwargs):
    from ai.mva.inference import create_violation_event, track_and_detect
    source = kwargs.get("source")
    if os.getenv("TIER3_USE_VIDEO_TRACKER", "false").lower() == "true" and isinstance(source, (str, os.PathLike)):
        return track_and_detect(str(source), latitude=kwargs.get("latitude"),
                                longitude=kwargs.get("longitude"), bus_id=kwargs.get("bus_id"),
                                camera_id=kwargs.get("camera_id"))
    image = kwargs.get("image") or source
    if image is None:
        raise ValueError("Tier 3 requires an image/frame or video source")
    return create_violation_event(
        violation_type=os.getenv("TIER3_DEFAULT_VIOLATION", "TRAFFIC_RULE_VIOLATION"),
        image=image, latitude=kwargs.get("latitude"), longitude=kwargs.get("longitude"),
        timestamp=kwargs.get("timestamp"), bus_id=kwargs.get("bus_id"),
        camera_id=kwargs.get("camera_id"),
    )


def build_pipeline() -> UrbanSensePipeline:
    return UrbanSensePipeline(
        tier1=_tier1_adapter if os.getenv("TIER1_MODEL_PATH") else None,
        tier2=_tier2_adapter if os.getenv("TIER2_MODEL_PATH") or os.getenv("TIER2_ENABLED", "false").lower() == "true" else None,
        tier3=_tier3_adapter if os.getenv("TIER3_MODEL_PATH") else None,
    )


def build_demo_pipeline() -> UrbanSensePipeline:
    return UrbanSensePipeline()
