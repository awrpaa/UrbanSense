# UrbanSense Backend

FastAPI orchestration layer for the three UrbanSense intelligence tiers.

## Architecture

- Tier 1: road defects and sinkhole-risk assessment
- Tier 2: fleet traffic intelligence with external TomTom fallback
- Tier 3: MVA/violation and ANPR evidence pipeline
- Event fusion: combines repeated geospatial observations
- API: exposes normalized events to the web dashboard

The backend deliberately separates model inference from the API. Training notebooks remain experimental/reproducibility artifacts; production adapters should load trained weights from local deployment storage or a model registry.

## Local run

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open `/docs` on the local server.

Never commit `.env`, API keys, model weights, datasets, or evidence containing sensitive plate data.
