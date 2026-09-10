from math import cos, radians
from typing import Iterable

from backend.schemas.events import UrbanSenseEvent


def _distance_m(a: UrbanSenseEvent, b: UrbanSenseEvent) -> float:
    if not a.location or not b.location:
        return float("inf")
    lat = radians((a.location.latitude + b.location.latitude) / 2)
    dlat = (a.location.latitude - b.location.latitude) * 111_320
    dlon = (a.location.longitude - b.location.longitude) * 111_320 * cos(lat)
    return (dlat * dlat + dlon * dlon) ** 0.5


def fuse_road_events(events: Iterable[UrbanSenseEvent], radius_m: float = 35.0) -> list[UrbanSenseEvent]:
    """Fuse nearby Tier-1 observations into verified road-defect events.

    Prototype rule: observations within radius_m are grouped. Production should
    additionally constrain clusters by road segment and time window.
    """
    candidates = [e for e in events if e.tier == 1 and e.event_type == "ROAD_DEFECT"]
    used: set[int] = set()
    fused: list[UrbanSenseEvent] = []

    for i, event in enumerate(candidates):
        if i in used:
            continue
        cluster = [event]
        used.add(i)
        for j in range(i + 1, len(candidates)):
            other = candidates[j]
            if j not in used and _distance_m(event, other) <= radius_m:
                cluster.append(other)
                used.add(j)

        if len(cluster) == 1:
            fused.append(event)
            continue

        best = max(cluster, key=lambda e: e.confidence or 0.0)
        metadata = dict(best.metadata)
        metadata.update({
            "observation_count": len(cluster),
            "verification": "MULTI_FLEET",
            "source_event_ids": [e.event_id for e in cluster],
        })
        fused.append(best.model_copy(update={
            "event_id": f"VERIFIED-{best.event_id}",
            "event_type": "VERIFIED_ROAD_DEFECT",
            "metadata": metadata,
        }))

    return fused
