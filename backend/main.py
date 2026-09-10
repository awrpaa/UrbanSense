from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()

from backend.pipeline import build_pipeline
from backend.schemas.events import EventBatch
from backend.services.tomtom import flow_segment

app = FastAPI(
    title="UrbanSense API",
    version="0.5.1",
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

KOLKATA_TRAFFIC_POINTS = {
    "AJC Bose Road": (22.5456, 88.3530),
    "Park Street": (22.5535, 88.3510),
    "EM Bypass": (22.5120, 88.4000),
    "VIP Road": (22.6100, 88.4100),
    "Jadavpur": (22.4970, 88.3690),
    "Howrah Bridge": (22.5850, 88.3420),
    "M G Road": (22.5720, 88.3630),
    "Rashbehari Avenue": (22.5190, 88.3510),
    "Jessore Road": (22.6200, 88.4300),
    "Diamond Harbour Road": (22.5000, 88.3250),
}

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
    return {"status":"ok","service":"urbansense-backend","pipeline":"tier1-tier2-tier3","enabled_tiers":enabled,"models":"configured" if enabled else "not_configured"}

@app.post("/api/events/validate")
def validate_events(batch: EventBatch):
    return {"valid":True,"count":len(batch.events),"events":[event.model_dump(mode="json") for event in batch.events]}

@app.post("/api/pipeline/process")
def process_pipeline(request: ProcessRequest):
    tiers = sorted(set(request.tiers))
    if any(tier not in (1,2,3) for tier in tiers):
        raise HTTPException(status_code=400, detail="tiers must contain only 1,2,3")
    if request.image_path is not None and not Path(request.image_path).exists():
        raise HTTPException(status_code=400, detail=f"Image not found: {request.image_path}")
    if request.source_path is not None and not Path(request.source_path).exists():
        raise HTTPException(status_code=400, detail=f"Source not found: {request.source_path}")
    if request.image_path is None and request.source_path is None:
        raise HTTPException(status_code=400, detail="Provide image_path or source_path")
    try:
        events = pipeline.process(image=request.image_path,source=request.source_path,latitude=request.latitude,longitude=request.longitude,timestamp=datetime.now(timezone.utc),bus_id=request.bus_id,camera_id=request.camera_id,tiers=tiers)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"count":len(events),"events":[event.model_dump(mode="json") for event in events]}

def _read_traffic_point(item: tuple[str, tuple[float, float]]) -> dict:
    name,(latitude,longitude)=item
    try:
        data=flow_segment(latitude,longitude,timeout=8.0)
        return {"name":name,"latitude":latitude,"longitude":longitude,**data,"status":"LIVE"}
    except Exception as exc:
        return {"name":name,"latitude":latitude,"longitude":longitude,"status":"UNAVAILABLE","error":str(exc)}

@app.get("/api/traffic/dashboard")
def traffic_dashboard():
    results=[]
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures=[executor.submit(_read_traffic_point,item) for item in KOLKATA_TRAFFIC_POINTS.items()]
        for future in as_completed(futures): results.append(future.result())
    results.sort(key=lambda row:list(KOLKATA_TRAFFIC_POINTS).index(row["name"]))
    live=[row for row in results if row.get("status")=="LIVE" and row.get("score") is not None]
    average_score=round(sum(row["score"] for row in live)/len(live),1) if live else None
    average_speed=round(sum(row["current_speed"] for row in live)/len(live),1) if live else None
    average_free_flow=round(sum(row["free_flow_speed"] for row in live)/len(live),1) if live else None
    city_level="UNKNOWN" if average_score is None else "LOW" if average_score<20 else "MEDIUM" if average_score<50 else "HIGH"
    return {"source":"TOMTOM","fleet_status":"OFFLINE","city":"Kolkata","updated_at":datetime.now(timezone.utc).isoformat(),"refresh_hint_seconds":120,"summary":{"score":average_score,"level":city_level,"average_speed":average_speed,"average_free_flow_speed":average_free_flow,"live_segments":len(live),"total_segments":len(results)},"points":results}

@app.post("/api/traffic/fallback")
def traffic_fallback(point: TrafficPoint):
    try: result=flow_segment(point.latitude,point.longitude)
    except RuntimeError as exc: raise HTTPException(status_code=503,detail=str(exc)) from exc
    except Exception as exc: raise HTTPException(status_code=502,detail=f"TomTom request failed: {exc}") from exc
    return {"source":"TOMTOM","fleet_status":"OFFLINE","latitude":point.latitude,"longitude":point.longitude,**result}
