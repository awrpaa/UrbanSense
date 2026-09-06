# Traffic Intelligence

Prototype traffic-perception pipeline:

`YOLO11 → multi-object tracking → vehicle count / occupancy / relative motion → temporal congestion scoring → UrbanSense event`

The system is designed for moving bus cameras, so congestion is inferred from temporal traffic behaviour rather than a single-frame vehicle count.