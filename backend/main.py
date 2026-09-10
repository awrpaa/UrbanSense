from datetime import datetime

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.pipeline import build_demo_pipeline
from backend.schemas.events import EventBatch
from backend.services.tomtom import flow_segment

app = FastAPI(
    title="UrbanSense API",
    version="0.2.0",
    description="Unified API for UrbanSense road, traffic and MVA intelligence.",
)

pipeline = build_demo_pipeline()


class TrafficPoint(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "urbansense-backend",
        "pipeline": "tier1-tier2-tier3",
        "models": "adapter-ready",
    }


@app.post("/api/events/validate")
def validate_events(batch: EventBatch):
    return {
        "valid": True,
        "count": len(batch.events),
        "events": [event.model_dump(mode="json") for event in batch.events],
    }


@app.post("/api/pipeline/process")
def process_pipeline(point: TrafficPoint):
    """Run configured AI adapters on an input point/frame.

    Model adapters are intentionally injected into UrbanSensePipeline. Until the
    deployment weights are installed, this endpoint returns an empty event list.
    """
    events = pipeline.process(
        latitude=point.latitude,
        longitude=point.longitude,
        timestamp=datetime.now(),
    )
    return {"count": len(events), "events": [e.model_dump(mode="json") for e in events]}


@app.post("/api/traffic/fallback")
def traffic_fallback(point: TrafficPoint):
    """Get live TomTom segment traffic when fleet sensing is unavailable."""
    try:
        result = flow_segment(point.latitude, point.longitude)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"TomTom request failed: {exc}") from exc

    return {
        "source": "TOMTOM",
        "fleet_status": "OFFLINE",
        "latitude": point.latitude,
        "longitude": point.longitude,
        **result,
    }
