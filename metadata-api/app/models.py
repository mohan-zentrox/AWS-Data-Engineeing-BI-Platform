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
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base

SCHEMA = "quarry_metadata"

# run_id is `UUID PRIMARY KEY` in schema.sql. Declaring it as plain String
# here is not enough: writes round-trip fine (psycopg2 casts the text), but on
# *read* psycopg2 hands back a uuid.UUID for the uuid type OID no matter what
# the SQLAlchemy column says, which then fails PipelineRunOut validation. The
# postgresql variant with as_uuid=False makes the Postgres read path return a
# string, matching what SQLite (this service's test backend, which has no
# native UUID type) already returns.
RunIdType = String(36).with_variant(PostgresUUID(as_uuid=False), "postgresql")


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = {"schema": SCHEMA}

    run_id: Mapped[str] = mapped_column(RunIdType, primary_key=True)
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
