"""UrbanSense end-to-end integration smoke test.

Run this on the machine/Colab runtime where model weights and test media are mounted.
Nothing in this script requires model files to be committed to Git.

Examples:
  python scripts/integration_check.py --tier1-image /path/frame.jpg
  python scripts/integration_check.py --tier2-video /path/traffic.mp4
  python scripts/integration_check.py --tier3-image /path/violation.jpg
  python scripts/integration_check.py --tier1-image frame.jpg --tier2-video traffic.mp4 --tier3-image violation.jpg
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.schemas.events import UrbanSenseEvent
from backend.pipeline import UrbanSensePipeline, _tier1_adapter, _tier2_adapter, _tier3_adapter
from backend.services.event_fusion import fuse_road_events


def check_file(label: str, path: str | None) -> tuple[bool, str]:
    if not path:
        return False, f"{label}: SKIP (no input supplied)"
    p = Path(path)
    if not p.exists():
        return False, f"{label}: FAIL (missing: {p})"
    return True, f"{label}: READY ({p})"


def run_tier1(path: str) -> tuple[bool, list[UrbanSenseEvent], str]:
    try:
        raw = _tier1_adapter(image=path, timestamp=datetime.now(timezone.utc), bus_id="DEMO-BUS", camera_id="FRONT")
        events = [UrbanSenseEvent.model_validate(x) for x in raw]
        return True, events, f"Tier 1: PASS ({len(events)} events)"
    except Exception as exc:
        return False, [], f"Tier 1: FAIL ({type(exc).__name__}: {exc})"


def run_tier2(path: str) -> tuple[bool, list[UrbanSenseEvent], str]:
    try:
        raw = _tier2_adapter(source=path, timestamp=datetime.now(timezone.utc), bus_id="DEMO-BUS", camera_id="FRONT")
        events = [UrbanSenseEvent.model_validate(x) for x in raw]
        return True, events, f"Tier 2: PASS ({len(events)} events)"
    except Exception as exc:
        return False, [], f"Tier 2: FAIL ({type(exc).__name__}: {exc})"


def run_tier3(path: str) -> tuple[bool, list[UrbanSenseEvent], str]:
    try:
        raw = _tier3_adapter(image=path, timestamp=datetime.now(timezone.utc), bus_id="DEMO-BUS", camera_id="FRONT")
        events = [UrbanSenseEvent.model_validate(x) for x in raw]
        return True, events, f"Tier 3: PASS ({len(events)} events)"
    except Exception as exc:
        return False, [], f"Tier 3: FAIL ({type(exc).__name__}: {exc})"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tier1-image")
    parser.add_argument("--tier2-video")
    parser.add_argument("--tier3-image")
    parser.add_argument("--output", default="integration_report.json")
    args = parser.parse_args()

    results = []
    all_events: list[UrbanSenseEvent] = []

    for label, path in [("Tier 1 input", args.tier1_image), ("Tier 2 input", args.tier2_video), ("Tier 3 input", args.tier3_image)]:
        ok, message = check_file(label, path)
        results.append({"check": label, "status": "READY" if ok else "SKIP/FAIL", "message": message})
        print(message)

    if args.tier1_image and Path(args.tier1_image).exists():
        ok, events, message = run_tier1(args.tier1_image); print(message)
        results.append({"check": "Tier 1 inference", "status": "PASS" if ok else "FAIL", "message": message}); all_events += events
    if args.tier2_video and Path(args.tier2_video).exists():
        ok, events, message = run_tier2(args.tier2_video); print(message)
        results.append({"check": "Tier 2 inference", "status": "PASS" if ok else "FAIL", "message": message}); all_events += events
    if args.tier3_image and Path(args.tier3_image).exists():
        ok, events, message = run_tier3(args.tier3_image); print(message)
        results.append({"check": "Tier 3 inference", "status": "PASS" if ok else "FAIL", "message": message}); all_events += events

    schema_ok = True
    try:
        validated = [UrbanSenseEvent.model_validate(e.model_dump()) for e in all_events]
        print(f"Event schema: PASS ({len(validated)} events validated)")
    except Exception as exc:
        schema_ok = False
        print(f"Event schema: FAIL ({exc})")
    results.append({"check": "Shared event schema", "status": "PASS" if schema_ok else "FAIL", "message": "All emitted events validate as UrbanSenseEvent" if schema_ok else "Validation error"})

    road_events = [e for e in all_events if e.tier == 1 and e.event_type == "ROAD_DEFECT"]
    fused = fuse_road_events(road_events)
    print(f"Event fusion: PASS ({len(road_events)} road observations -> {len(fused)} fused events)")
    results.append({"check": "Road event fusion", "status": "PASS", "message": f"{len(road_events)} observations -> {len(fused)} fused events"})

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "weights_are_external": True,
        "results": results,
        "event_counts": {
            "total": len(all_events),
            "tier1": sum(e.tier == 1 for e in all_events),
            "tier2": sum(e.tier == 2 for e in all_events),
            "tier3": sum(e.tier == 3 for e in all_events),
            "fused_road": len(fused),
        },
        "sample_events": [e.model_dump(mode="json") for e in all_events[:20]],
    }
    Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report written to {args.output}")
    return 0 if schema_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
