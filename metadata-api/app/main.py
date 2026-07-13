"""Project Quarry metadata/status API.

Exposes the Postgres metadata store (libs/metadata_client/schema.sql) over
HTTP: pipeline run history and the dataset catalog. This is the "metadata/
status API" platform service documented in the FRD.

Run locally:
    uvicorn app.main:app --reload --port 8000

Or via docker-compose (see repo-root docker-compose.yml, service
`metadata-api`).
"""
from __future__ import annotations

from fastapi import FastAPI

from .routers import catalog, pipelines

app = FastAPI(
    title="Project Quarry Metadata API",
    description="Pipeline run history and dataset catalog, backed by the Postgres metadata store.",
    version="0.1.0",
)

app.include_router(pipelines.router)
app.include_router(catalog.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
