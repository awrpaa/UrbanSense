from math import cos, radians
from collections import defaultdict
from typing import Iterable

from schemas.events import UrbanSenseEvent


def _distance_m(a: UrbanSenseEvent, b: UrbanSenseEvent) -> float:
    if not a.location or not b.location:
        return float("inf")
    lat = radians((a.location.latitude + b.location.latitude) / 2)
    dlat = (a.location.latitude - b.location.latitude) * 111_320
    dlon = (a.location.longitude - b.location.longitude) * 111_320 * cos(lat)
    return (dlat * dlat + dlon * dlon) ** 0.5


def fuse_road_events(events: Iterable[UrbanSenseEvent], radius_m: float = 35.0) -> list[UrbanSenseEvent]:
    """Collapse nearby Tier-1 observations of the same defect into verified events."""
    candidates = [e for e in events if e.tier == 1 and e.event_type == "ROAD_DEFECT"]
    used: set[int] = set()
    fused: list[UrbanSenseEvent] = []

    for i, event in enumerate(candidates):
        if i in used:
            continue
        cluster = [event]
        used.add(i)
        for j in range(i + 1, len(candidates)):
            if j not in used and _distance_m(event, candidates[j]) <= radius_m:
                cluster.append(candidates[j])
                used.add(j)

        if len(cluster) == 1:
            fused.append(event)
            continue

        observations = len(cluster)
        best_conf = max((e.confidence or 0.0) for e in cluster)
        location = event.location
        metadata = dict(event.metadata)
        metadata.update({"observation_count": observations, "verification": "MULTI_FLEET"})
        fused.append(event.model_copy(update={
            "event_id": f"VERIFIED-{event.event_id}",
            "event_type": "VERIFIED_ROAD_DEFECT",
            "confidence": best_conf,
            "metadata": metadata,
        }))

    return fused
