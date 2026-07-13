"""MetadataClient — small internal client library for Project Quarry's
Postgres metadata store (schema.sql in this package).

Used by:
  - airflow/dags/sales_orders_pipeline.py to write run state
    (start/end/status/rowcount) for every pipeline execution.
  - metadata-api/app/db.py (read-side) exposes the same tables over HTTP.

Design notes:
  - psycopg2 is the only runtime dependency, kept deliberately light so this
    package can be installed inside Airflow workers without dependency
    conflicts.
  - The database connection is created lazily via an injectable
    `conn_factory`, which makes the client unit-testable without a real
    Postgres instance (see tests/test_client.py).
  - All methods open/close a connection per call rather than holding a long
    lived connection, which is the safer default for Airflow tasks that run
    in short-lived worker processes.
"""
from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Iterator, Optional

try:
    import psycopg2
    import psycopg2.extras
except ImportError:  # pragma: no cover - exercised only when psycopg2 absent
    psycopg2 = None

from .models import DatasetCatalogEntry, PipelineRun

DEFAULT_DSN_ENV_VAR = "METADATA_DATABASE_URL"


class MetadataClientError(RuntimeError):
    """Raised for metadata store operation failures."""


def _default_conn_factory(dsn: str):
    if psycopg2 is None:  # pragma: no cover
        raise MetadataClientError(
            "psycopg2 is not installed. Install libs/metadata_client's "
            "requirements.txt, or pass a conn_factory for testing."
        )
    return psycopg2.connect(dsn)


class MetadataClient:
    """Thin client over the ``quarry_metadata`` Postgres schema."""

    def __init__(
        self,
        dsn: Optional[str] = None,
        conn_factory: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self.dsn = dsn or os.environ.get(DEFAULT_DSN_ENV_VAR)
        if not self.dsn:
            raise MetadataClientError(
                f"No DSN provided and {DEFAULT_DSN_ENV_VAR} is not set."
            )
        self._conn_factory = conn_factory or _default_conn_factory

    @contextmanager
    def _cursor(self) -> Iterator[Any]:
        conn = self._conn_factory(self.dsn)
        try:
            with conn:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor if psycopg2 else None) as cur:
                    yield cur
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Pipeline runs
    # ------------------------------------------------------------------

    def start_run(
        self,
        pipeline_name: str,
        task_name: Optional[str] = None,
        dag_run_id: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> uuid.UUID:
        """Insert a 'running' row and return its run_id."""
        run_id = uuid.uuid4()
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO quarry_metadata.pipeline_runs
                    (run_id, pipeline_name, task_name, dag_run_id, status, started_at, extra)
                VALUES (%s, %s, %s, %s, 'running', %s, %s)
                """,
                (
                    str(run_id),
                    pipeline_name,
                    task_name,
                    dag_run_id,
                    datetime.now(timezone.utc),
                    json.dumps(extra or {}),
                ),
            )
        return run_id

    def complete_run(
        self,
        run_id: uuid.UUID,
        status: str,
        row_count: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        if status not in ("success", "failed"):
            raise MetadataClientError(f"Invalid terminal status: {status!r}")
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE quarry_metadata.pipeline_runs
                SET status = %s, ended_at = %s, row_count = %s, error_message = %s
                WHERE run_id = %s
                """,
                (status, datetime.now(timezone.utc), row_count, error_message, str(run_id)),
            )

    @contextmanager
    def run(
        self,
        pipeline_name: str,
        task_name: Optional[str] = None,
        dag_run_id: Optional[str] = None,
    ) -> Iterator[Callable[[Optional[int]], None]]:
        """Context manager that starts a run and auto-completes it.

        Usage::

            with metadata_client.run("sales_orders_pipeline", task_name="clean") as set_row_count:
                df = clean(df)
                set_row_count(len(df))
        """
        run_id = self.start_run(pipeline_name, task_name=task_name, dag_run_id=dag_run_id)
        row_count_holder: dict[str, Optional[int]] = {"value": None}

        def _set_row_count(n: Optional[int]) -> None:
            row_count_holder["value"] = n

        try:
            yield _set_row_count
        except Exception as exc:
            self.complete_run(run_id, status="failed", error_message=str(exc))
            raise
        else:
            self.complete_run(run_id, status="success", row_count=row_count_holder["value"])

    def get_runs(self, pipeline_name: str, limit: int = 50) -> list[PipelineRun]:
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT run_id, pipeline_name, task_name, dag_run_id, status,
                       started_at, ended_at, row_count, error_message, extra
                FROM quarry_metadata.pipeline_runs
                WHERE pipeline_name = %s
                ORDER BY started_at DESC
                LIMIT %s
                """,
                (pipeline_name, limit),
            )
            rows = cur.fetchall()
        return [PipelineRun.from_row(dict(r)) for r in rows]

    # ------------------------------------------------------------------
    # Watermarks
    # ------------------------------------------------------------------

    def get_watermark(self, pipeline_name: str, dataset_name: str) -> Optional[str]:
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT watermark_value FROM quarry_metadata.watermarks
                WHERE pipeline_name = %s AND dataset_name = %s
                """,
                (pipeline_name, dataset_name),
            )
            row = cur.fetchone()
        return row["watermark_value"] if row else None

    def set_watermark(self, pipeline_name: str, dataset_name: str, value: str) -> None:
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO quarry_metadata.watermarks (pipeline_name, dataset_name, watermark_value, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (pipeline_name, dataset_name)
                DO UPDATE SET watermark_value = EXCLUDED.watermark_value, updated_at = EXCLUDED.updated_at
                """,
                (pipeline_name, dataset_name, value, datetime.now(timezone.utc)),
            )

    # ------------------------------------------------------------------
    # Dataset catalog
    # ------------------------------------------------------------------

    def register_dataset(
        self,
        dataset_name: str,
        zone: str,
        location: str,
        owner_role: str,
        description: Optional[str] = None,
    ) -> None:
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO quarry_metadata.dataset_catalog
                    (dataset_name, zone, location, owner_role, description, last_updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (dataset_name)
                DO UPDATE SET zone = EXCLUDED.zone, location = EXCLUDED.location,
                              owner_role = EXCLUDED.owner_role, description = EXCLUDED.description
                """,
                (dataset_name, zone, location, owner_role, description, datetime.now(timezone.utc)),
            )

    def touch_dataset(self, dataset_name: str) -> None:
        with self._cursor() as cur:
            cur.execute(
                """
                UPDATE quarry_metadata.dataset_catalog
                SET last_updated_at = %s
                WHERE dataset_name = %s
                """,
                (datetime.now(timezone.utc), dataset_name),
            )

    def list_catalog(self) -> list[DatasetCatalogEntry]:
        with self._cursor() as cur:
            cur.execute(
                """
                SELECT dataset_name, zone, location, owner_role, description,
                       last_updated_at, created_at
                FROM quarry_metadata.dataset_catalog
                ORDER BY dataset_name
                """
            )
            rows = cur.fetchall()
        return [DatasetCatalogEntry.from_row(dict(r)) for r in rows]

    # ------------------------------------------------------------------
    # Lineage
    # ------------------------------------------------------------------

    def record_lineage(self, upstream_dataset: str, downstream_dataset: str, pipeline_name: str) -> None:
        with self._cursor() as cur:
            cur.execute(
                """
                INSERT INTO quarry_metadata.lineage_edges (upstream_dataset, downstream_dataset, pipeline_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (upstream_dataset, downstream_dataset, pipeline_name) DO NOTHING
                """,
                (upstream_dataset, downstream_dataset, pipeline_name),
            )
