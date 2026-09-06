# UrbanSense

**AI-powered mobile urban intelligence using public transport fleets.**

UrbanSense turns existing public buses into a distributed sensing network. On-board computer vision analyses road conditions, traffic and motor-vehicle violations, then converts detections into geotagged events for centralized urban intelligence.

## Core pipeline

`Bus Cameras + GPS/IMU → Edge AI → UrbanSense Events → Backend/GIS → Dashboard → Action`

## AI tiers

### Tier 1 — Road Intelligence
YOLO11n-based road-damage detection trained on a unified RDD2022-derived YOLO dataset. Current classes:
- Longitudinal Crack (D00)
- Transverse Crack (D10)
- Alligator Crack (D20)
- Pothole (D40)

### Tier 2 — Traffic Intelligence
YOLO11 + OpenCV + ByteTrack-style multi-object tracking and temporal analytics for vehicle counting, density, congestion and traffic anomalies.

### Tier 3 — MVA & Violation Detection
YOLO11 + ByteTrack + EasyOCR for vehicle/rider/helmet/plate perception, ANPR/OCR and violation evidence generation. Prototype violations include no-helmet and traffic-rule events.

### Accident Detection
The architecture supports collision-like and abnormal-motion detection using object tracking and temporal motion analysis.

## UrbanSense Event

Each detection is normalized into an event containing fields such as event type, bus/camera ID, timestamp, GPS, confidence, severity and evidence reference. This enables a common interface across all AI tiers.

## Dashboard prototype

The prototype provides a GIS-centered operational view with congestion heatmaps, incident markers, bus routes, event feeds, camera evidence and analytics.

## Repository structure

```text
ai/          AI tier code and inference
common/      shared event schema and adapters
dashboard/   dashboard prototype assets
models/      model documentation / release references
notebooks/   training and experiment notebooks
docs/        architecture and presentation assets
```

## Reproducibility

Large datasets and training artifacts are intentionally not stored in Git. Download the referenced datasets separately and place trained weights under `models/` locally.

## Security & privacy

Production deployment should use TLS, role-based access control, secure authentication, encryption at rest, audit logging and data minimization for ANPR/evidence data.

## Status

Prototype / hackathon implementation. Road-damage training is validated on GPU; Tier 2 and Tier 3 pipelines are available as prototype inference/event-generation components.
