"""Train UrbanSense road-damage detector.

Requires the UrbanSense YOLO-format dataset and Ultralytics.
"""
from ultralytics import YOLO

DATA = "urbansense.yaml"

model = YOLO("yolo11n.pt")
model.train(
    data=DATA,
    epochs=50,
    imgsz=640,
    batch=16,
    device=0,
    project="checkpoints",
    name="road_damage_v1",
    save=True,
    save_period=5,
    patience=10,
    workers=2,
    degrees=5,
    translate=0.1,
    scale=0.5,
    fliplr=0.5,
)
