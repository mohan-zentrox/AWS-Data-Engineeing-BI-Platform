"""GET /pipelines/{name}/runs — pipeline run history.

Reads quarry_metadata.pipeline_runs, the same table
airflow/dags/sales_orders_pipeline.py writes to via
libs/metadata_client.MetadataClient.start_run/complete_run.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import PipelineRun
from ..schemas import PipelineRunOut, PipelineRunsResponse

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


@router.get("/{name}/runs", response_model=PipelineRunsResponse)
def get_pipeline_runs(
    name: str,
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> PipelineRunsResponse:
    stmt = (
        select(PipelineRun)
        .where(PipelineRun.pipeline_name == name)
        .order_by(PipelineRun.started_at.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).scalars().all()
    runs = [PipelineRunOut.model_validate(r) for r in rows]
    return PipelineRunsResponse(pipeline_name=name, run_count=len(runs), runs=runs)
