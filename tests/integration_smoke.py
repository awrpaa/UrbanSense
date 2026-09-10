"""Lightweight integration checks for the UrbanSense AI/backend contract.

Run from repository root after installing backend + AI requirements:
    python tests/integration_smoke.py

This test does not require model weights unless RUN_MODEL_TESTS=1.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

# Allow `python tests/integration_smoke.py` from repository root.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.schemas.events import UrbanSenseEvent
from backend.services.event_fusion import fuse_road_events


def check_schema_and_fusion() -> None:
    now = datetime.now(timezone.utc)
    events = [
        UrbanSenseEvent(
            event_id="ROAD-A", tier=1, event_type="ROAD_DEFECT", timestamp=now,
            location={"latitude": 22.5726, "longitude": 88.3639},
            confidence=0.91, severity="HIGH", source="FLEET",
            metadata={"defect_type": "Pothole"},
        ),
        UrbanSenseEvent(
            event_id="ROAD-B", tier=1, event_type="ROAD_DEFECT", timestamp=now,
            location={"latitude": 22.5727, "longitude": 88.3640},
            confidence=0.88, severity="HIGH", source="FLEET",
            metadata={"defect_type": "Pothole"},
        ),
    ]
    fused = fuse_road_events(events, radius_m=35)
    assert len(fused) == 1, "Expected nearby fleet observations to fuse"
    assert fused[0].event_type == "VERIFIED_ROAD_DEFECT"
    assert fused[0].metadata["observation_count"] == 2
    print("PASS  schema + multi-fleet road-event fusion")


def check_pipeline_configuration() -> None:
    from backend.pipeline import build_pipeline
    pipeline = build_pipeline()
    print("PASS  pipeline import/configuration; enabled tiers:",
          [k for k, v in pipeline.adapters.items() if v is not None])


def check_model_adapters() -> None:
    if os.getenv("RUN_MODEL_TESTS", "0") != "1":
        print("SKIP model inference (set RUN_MODEL_TESTS=1 to enable)")
        return

    required = {
        1: os.getenv("TIER1_MODEL_PATH", ""),
        3: os.getenv("TIER3_MODEL_PATH", ""),
    }
    for tier, path in required.items():
        if not path or not os.path.exists(path):
            print(f"SKIP Tier {tier} model: path not configured")
        else:
            print(f"FOUND Tier {tier} model: {path}")

    if os.getenv("TIER2_ENABLED", "false").lower() == "true":
        print("Tier 2 enabled:", os.getenv("TIER2_MODEL_PATH", "yolo26s.pt"))


def main() -> None:
    check_schema_and_fusion()
    check_pipeline_configuration()
    check_model_adapters()
    print("UrbanSense integration smoke test complete.")


if __name__ == "__main__":
    main()
