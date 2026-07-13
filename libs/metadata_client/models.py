"""Typed value objects returned by MetadataClient.

Kept dependency-free (stdlib dataclasses only) so both the Airflow workers
and the metadata-api service can share these types without pulling in
SQLAlchemy or FastAPI on the Airflow side.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import UUID


@dataclass
class PipelineRun:
    run_id: UUID
    pipeline_name: str
    task_name: Optional[str]
    dag_run_id: Optional[str]
    status: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    row_count: Optional[int] = None
    error_message: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "PipelineRun":
        return cls(
            run_id=row["run_id"],
            pipeline_name=row["pipeline_name"],
            task_name=row.get("task_name"),
            dag_run_id=row.get("dag_run_id"),
            status=row["status"],
            started_at=row["started_at"],
            ended_at=row.get("ended_at"),
            row_count=row.get("row_count"),
            error_message=row.get("error_message"),
            extra=row.get("extra") or {},
        )


@dataclass
class DatasetCatalogEntry:
    dataset_name: str
    zone: str
    location: str
    owner_role: str
    description: Optional[str]
    last_updated_at: Optional[datetime]
    created_at: datetime

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "DatasetCatalogEntry":
        return cls(
            dataset_name=row["dataset_name"],
            zone=row["zone"],
            location=row["location"],
            owner_role=row["owner_role"],
            description=row.get("description"),
            last_updated_at=row.get("last_updated_at"),
            created_at=row["created_at"],
        )
