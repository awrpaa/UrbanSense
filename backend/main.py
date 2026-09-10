from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from backend.pipeline import build_pipeline
from backend.schemas.events import EventBatch
from backend.services.tomtom import flow_segment

app = FastAPI(
    title="UrbanSense API",
    version="0.3.0",
    description="Unified API for UrbanSense road, traffic and MVA intelligence.",
)

pipeline = build_pipeline()


class TrafficPoint(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class ProcessRequest(TrafficPoint):
    tiers: list[int] = Field(default_factory=lambda: [1, 2, 3])
    bus_id: str | None = None
    camera_id: str | None = None


@app.get("/api/health")
def health():
    enabled = [tier for tier, adapter in pipeline.adapters.items() if adapter is not None]
    return {
        "status": "ok",
        "service": "urbansense-backend",
        "pipeline": "tier1-tier2-tier3",
        "enabled_tiers": enabled,
        "models": "configured" if enabled else "not_configured",
    }


@app.post("/api/events/validate")
def validate_events(batch: EventBatch):
    return {
        "valid": True,
        "count": len(batch.events),
        "events": [event.model_dump(mode="json") for event in batch.events],
    }


@app.post("/api/pipeline/process")
def process_pipeline(request: ProcessRequest):
    """Run configured adapters when the caller supplies the corresponding frame/source."""
    try:
        events = pipeline.process(
            latitude=request.latitude,
            longitude=request.longitude,
            timestamp=datetime.now(timezone.utc),
            bus_id=request.bus_id,
            camera_id=request.camera_id,
            tiers=request.tiers,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
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
