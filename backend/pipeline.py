from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Optional

from backend.schemas.events import UrbanSenseEvent


class UrbanSensePipeline:
    """Orchestrates Tier 1/2/3 adapters behind one event interface.

    Adapters are injected so the web API never needs to know model internals.
    """

    def __init__(
        self,
        tier1: Optional[Callable[..., Iterable[UrbanSenseEvent]]] = None,
        tier2: Optional[Callable[..., Iterable[UrbanSenseEvent]]] = None,
        tier3: Optional[Callable[..., Iterable[UrbanSenseEvent]]] = None,
    ) -> None:
        self.adapters = {1: tier1, 2: tier2, 3: tier3}

    def process(self, *, image: Any = None, latitude: Optional[float] = None,
                longitude: Optional[float] = None, timestamp: Optional[datetime] = None,
                bus_id: Optional[str] = None, camera_id: Optional[str] = None,
                tiers: Optional[list[int]] = None) -> list[UrbanSenseEvent]:
        timestamp = timestamp or datetime.now(timezone.utc)
        selected = tiers or [1, 2, 3]
        events: list[UrbanSenseEvent] = []
        context = {
            "image": image, "latitude": latitude, "longitude": longitude,
            "timestamp": timestamp, "bus_id": bus_id, "camera_id": camera_id,
        }
        for tier in selected:
            adapter = self.adapters.get(tier)
            if adapter is not None:
                events.extend(adapter(**context))
        return events


def build_demo_pipeline() -> UrbanSensePipeline:
    return UrbanSensePipeline()
