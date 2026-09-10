from fastapi import FastAPI

from backend.schemas.events import EventBatch

app = FastAPI(
    title="UrbanSense API",
    version="0.1.0",
    description="Unified API for UrbanSense road, traffic and MVA intelligence.",
)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "urbansense-backend",
        "pipeline": "tier1-tier2-tier3",
    }


@app.post("/api/events/validate")
def validate_events(batch: EventBatch):
    """Validate the canonical event envelope before database integration."""
    return {
        "valid": True,
        "count": len(batch.events),
        "events": [event.model_dump(mode="json") for event in batch.events],
    }
