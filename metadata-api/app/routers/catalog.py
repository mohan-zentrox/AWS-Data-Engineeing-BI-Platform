"""GET /catalog — registered datasets and their last-updated timestamp.

Reads quarry_metadata.dataset_catalog, written to by
airflow/dags/sales_orders_pipeline.py's write_curated task via
libs/metadata_client.MetadataClient.register_dataset/touch_dataset.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import DatasetCatalogEntry
from ..schemas import CatalogResponse, DatasetCatalogEntryOut

router = APIRouter(tags=["catalog"])


@router.get("/catalog", response_model=CatalogResponse)
def get_catalog(db: Session = Depends(get_db)) -> CatalogResponse:
    stmt = select(DatasetCatalogEntry).order_by(DatasetCatalogEntry.dataset_name)
    rows = db.execute(stmt).scalars().all()
    datasets = [DatasetCatalogEntryOut.model_validate(r) for r in rows]
    return CatalogResponse(dataset_count=len(datasets), datasets=datasets)
