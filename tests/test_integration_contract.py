from datetime import datetime, timezone

from backend.pipeline import UrbanSensePipeline
from backend.schemas.events import UrbanSenseEvent
from backend.services.event_fusion import fuse_road_events


def _event(event_id: str, lat: float, lon: float):
    return {
        "event_id": event_id,
        "tier": 1,
        "event_type": "ROAD_DEFECT",
        "timestamp": datetime.now(timezone.utc),
        "location": {"latitude": lat, "longitude": lon},
        "confidence": 0.9,
        "severity": "HIGH",
        "source": "FLEET",
        "evidence": {},
        "metadata": {"defect_type": "Pothole"},
    }


def test_pipeline_validates_common_event_contract():
    pipeline = UrbanSensePipeline(
        tier1=lambda **_: [_event("A", 22.57, 88.36)],
        tier2=lambda **_: [{
            "event_id": "T2", "tier": 2, "event_type": "TRAFFIC_CONGESTION",
            "timestamp": datetime.now(timezone.utc), "location": None,
            "confidence": None, "severity": "MEDIUM", "source": "FLEET",
            "evidence": {}, "metadata": {"vehicle_count": 5},
        }],
        tier3=lambda **_: [],
    )
    events = pipeline.process(image="frame.jpg", source="traffic.mp4")
    assert len(events) == 2
    assert all(isinstance(e, UrbanSenseEvent) for e in events)


def test_road_events_fuse_within_radius():
    events = [UrbanSenseEvent.model_validate(_event("A", 22.570000, 88.360000)),
              UrbanSenseEvent.model_validate(_event("B", 22.570100, 88.360100))]
    fused = fuse_road_events(events, radius_m=35)
    assert len(fused) == 1
    assert fused[0].event_type == "VERIFIED_ROAD_DEFECT"
    assert fused[0].metadata["observation_count"] == 2
