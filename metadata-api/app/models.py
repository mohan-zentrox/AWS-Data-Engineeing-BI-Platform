"""SQLAlchemy ORM models mapping onto libs/metadata_client/schema.sql.

Read-only usage from this service's perspective — writes to these tables
happen from Airflow via libs/metadata_client.MetadataClient. Keeping the
column set in sync with schema.sql is a manual contract for now (see
docs/ARCHITECTURE.md "Metadata store" section).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

SCHEMA = "quarry_metadata"

# run_id is stored as text rather than a dialect-specific UUID type so this
# model works unmodified against both Postgres (the real deployment target;
# the underlying column is still `UUID PRIMARY KEY` per schema.sql — text
# values round-trip through it transparently) and SQLite (used by this
# service's test suite, which has no native UUID type).


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = {"schema": SCHEMA}

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    pipeline_name: Mapped[str] = mapped_column(String, nullable=False)
    task_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    dag_run_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    row_count: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)


class DatasetCatalogEntry(Base):
    __tablename__ = "dataset_catalog"
    __table_args__ = {"schema": SCHEMA}

    dataset_name: Mapped[str] = mapped_column(String, primary_key=True)
    zone: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)
    owner_role: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
