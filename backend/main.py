from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.pipeline import build_pipeline
from backend.schemas.events import EventBatch
from backend.services.tomtom import flow_segment

app = FastAPI(
    title="UrbanSense API",
    version="0.4.0",
    description="Unified API for UrbanSense road, traffic and MVA intelligence.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline = build_pipeline()


class TrafficPoint(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class ProcessRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    image_path: Optional[str] = None
    source_path: Optional[str] = None
    tiers: list[int] = Field(default_factory=lambda: [1, 2, 3])
    bus_id: Optional[str] = None
    camera_id: Optional[str] = None


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
    tiers = sorted(set(request.tiers))
    if any(tier not in (1, 2, 3) for tier in tiers):
        raise HTTPException(status_code=400, detail="tiers must contain only 1,2,3")

    if request.image_path is not None and not Path(request.image_path).exists():
        raise HTTPException(status_code=400, detail=f"Image not found: {request.image_path}")
    if request.source_path is not None and not Path(request.source_path).exists():
        raise HTTPException(status_code=400, detail=f"Source not found: {request.source_path}")
    if request.image_path is None and request.source_path is None:
        raise HTTPException(status_code=400, detail="Provide image_path or source_path")

    try:
        events = pipeline.process(
            image=request.image_path,
            source=request.source_path,
            latitude=request.latitude,
            longitude=request.longitude,
            timestamp=datetime.now(timezone.utc),
            bus_id=request.bus_id,
            camera_id=request.camera_id,
            tiers=tiers,
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"count": len(events), "events": [event.model_dump(mode="json") for event in events]}


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
