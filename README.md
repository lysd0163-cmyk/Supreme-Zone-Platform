# Supreme Zone Platform

Institutional trading platform foundation.

## Run locally

```bash
pip install .
python main.py
```

## Deploy as web service

Use the Render blueprint in `render.yaml`.
The web entrypoint is:

```bash
uvicorn supreme_zone.webapp:app --host 0.0.0.0 --port $PORT
```
