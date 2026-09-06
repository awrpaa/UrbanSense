# Models

## Road Damage — `road_damage_v1`

- Architecture: YOLO11n
- Task: object detection
- Classes: longitudinal crack, transverse crack, alligator crack, pothole
- Dataset: unified RDD2022-derived YOLO-format road-damage dataset
- Training: GPU / Google Colab
- Checkpoints: maintained outside Git because model weights are binary artifacts

The trained checkpoint is maintained in the team's persistent storage. Copy the selected `.pt` checkpoint into this directory locally when running inference.

## Traffic

- YOLO11 pretrained vehicle detection
- Multi-object tracking
- Temporal density / occupancy / motion analysis
- Congestion scoring and event generation

## MVA / ANPR

- Vehicle and violation perception
- Multi-object tracking
- License-plate detection
- EasyOCR-based plate text extraction
- Confidence-aware evidence generation

## Accident Detection

Prototype architecture uses tracked-object motion and temporal anomaly analysis. This component should be treated as a prototype until validated on an accident-specific dataset.
