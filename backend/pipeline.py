from datetime import datetime, timezone
import os
from typing import Any, Optional

from backend.schemas.events import UrbanSenseEvent


class UrbanSensePipeline:
    """Orchestrate Tier 1/2/3 adapters behind one shared event contract."""

    def __init__(self, tier1=None, tier2=None, tier3=None) -> None:
        self.adapters = {1: tier1, 2: tier2, 3: tier3}

    def process(
        self, *, image: Any = None, source: Any = None,
        latitude: Optional[float] = None, longitude: Optional[float] = None,
        timestamp: Optional[datetime] = None, bus_id: Optional[str] = None,
        camera_id: Optional[str] = None, tiers: Optional[list[int]] = None,
    ) -> list[UrbanSenseEvent]:
        """Run selected adapters and validate every output against the event contract.

        image is a single frame for Tier 1/3. source is the video/image source
        for Tier 2; if omitted, Tier 2 falls back to image.
        """
        timestamp = timestamp or datetime.now(timezone.utc)
        selected = tiers or [1, 2, 3]
        events: list[UrbanSenseEvent] = []
        context = {
            "image": image, "source": source, "latitude": latitude,
            "longitude": longitude, "timestamp": timestamp,
            "bus_id": bus_id, "camera_id": camera_id,
        }
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
    return detect(**kwargs)


def _tier2_adapter(**kwargs):
    from ai.traffic.inference import track_video
    return track_video(
        kwargs.get("source") or kwargs.get("image"),
        latitude=kwargs.get("latitude"), longitude=kwargs.get("longitude"),
        timestamp=kwargs.get("timestamp"), bus_id=kwargs.get("bus_id"),
        camera_id=kwargs.get("camera_id"),
    )


def _tier3_adapter(**kwargs):
    from ai.mva.inference import create_violation_event
    violation = os.getenv("TIER3_DEFAULT_VIOLATION", "TRAFFIC_RULE_VIOLATION")
    return create_violation_event(violation_type=violation, **kwargs)


def build_pipeline() -> UrbanSensePipeline:
    """Build adapters enabled by environment configuration; weights load lazily."""
    return UrbanSensePipeline(
        tier1=_tier1_adapter if os.getenv("TIER1_MODEL_PATH") else None,
        tier2=_tier2_adapter if os.getenv("TIER2_MODEL_PATH") or os.getenv("TIER2_ENABLED", "false").lower() == "true" else None,
        tier3=_tier3_adapter if os.getenv("TIER3_PLATE_MODEL_PATH") else None,
    )


def build_demo_pipeline() -> UrbanSensePipeline:
    return UrbanSensePipeline()
