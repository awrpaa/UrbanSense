from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class Location(BaseModel):
    latitude: float
    longitude: float


class Evidence(BaseModel):
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    sha256: Optional[str] = None


class UrbanSenseEvent(BaseModel):
    """Canonical event envelope shared by all UrbanSense AI tiers."""

    event_id: str
    tier: Literal[1, 2, 3]
    event_type: str
    timestamp: datetime

    location: Optional[Location] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    severity: Optional[str] = None

    # Examples: FLEET, TOMTOM, SYSTEM
    source: str = "FLEET"

    evidence: Evidence = Field(default_factory=Evidence)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EventBatch(BaseModel):
    events: list[UrbanSenseEvent] = Field(default_factory=list)
