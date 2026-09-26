"""Pydantic response schemas for the metadata-api service."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class PipelineRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    pipeline_name: str
    task_name: Optional[str] = None
    dag_run_id: Optional[str] = None
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    row_count: Optional[int] = None
    error_message: Optional[str] = None
    extra: Optional[dict[str, Any]] = None

    @field_validator("run_id", mode="before")
    @classmethod
    def _coerce_run_id_to_str(cls, value: Any) -> Any:
        """Accept a uuid.UUID as well as a string for run_id.

        models.RunIdType already asks Postgres for strings, but a driver or
        dialect that returns uuid.UUID anyway should not turn a read into a
        500 — the JSON contract is the same either way.
        """
        return str(value) if isinstance(value, uuid.UUID) else value


class PipelineRunsResponse(BaseModel):
    pipeline_name: str
    run_count: int
    runs: list[PipelineRunOut]


class DatasetCatalogEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dataset_name: str
    zone: str
    location: str
    owner_role: str
    description: Optional[str] = None
    last_updated_at: Optional[datetime] = None
    created_at: datetime


class CatalogResponse(BaseModel):
    dataset_count: int
    datasets: list[DatasetCatalogEntryOut]
