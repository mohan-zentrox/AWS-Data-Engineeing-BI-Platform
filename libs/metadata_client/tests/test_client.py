"""Unit tests for MetadataClient.

These tests never touch a real Postgres instance: a fake connection/cursor
pair is injected via MetadataClient's `conn_factory` hook so the tests can
run in any environment (including this sandbox, which has no live database).
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from metadata_client.client import MetadataClient, MetadataClientError  # noqa: E402


class FakeCursor:
    def __init__(self, fetchone_result=None, fetchall_result=None):
        self.executed: list[tuple[str, tuple]] = []
        self._fetchone_result = fetchone_result
        self._fetchall_result = fetchall_result or []

    def execute(self, sql: str, params: tuple = ()):
        self.executed.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self._fetchone_result

    def fetchall(self):
        return self._fetchall_result

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class FakeConnection:
    def __init__(self, cursor: FakeCursor):
        self._cursor = cursor
        self.closed = False

    def cursor(self, cursor_factory=None):
        return self._cursor

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def close(self):
        self.closed = True


def make_client(cursor: FakeCursor) -> MetadataClient:
    conn = FakeConnection(cursor)
    return MetadataClient(dsn="postgresql://fake", conn_factory=lambda dsn: conn)


def test_requires_dsn():
    with pytest.raises(MetadataClientError):
        MetadataClient(dsn=None, conn_factory=lambda dsn: None)


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        # docker-compose.yml / .env.example set the SQLAlchemy-style form,
        # which libpq (psycopg2.connect) cannot parse.
        (
            "postgresql+psycopg2://u:p@host:5432/db",
            "postgresql://u:p@host:5432/db",
        ),
        ("postgres+psycopg2://u:p@host/db", "postgres://u:p@host/db"),
        # Already-libpq-compatible URLs and keyword/value DSNs pass through.
        ("postgresql://u:p@host/db", "postgresql://u:p@host/db"),
        ("host=localhost dbname=quarry_metadata", "host=localhost dbname=quarry_metadata"),
    ],
)
def test_dsn_strips_sqlalchemy_driver_suffix(given, expected):
    client = MetadataClient(dsn=given, conn_factory=lambda dsn: None)
    assert client.dsn == expected


def test_dsn_normalized_from_env(monkeypatch):
    monkeypatch.setenv(
        "METADATA_DATABASE_URL", "postgresql+psycopg2://u:p@postgres:5432/quarry_metadata"
    )
    client = MetadataClient(conn_factory=lambda dsn: None)
    assert client.dsn == "postgresql://u:p@postgres:5432/quarry_metadata"


def test_normalized_dsn_is_what_the_conn_factory_receives():
    seen: list[str] = []

    def factory(dsn: str):
        seen.append(dsn)
        return FakeConnection(FakeCursor())

    client = MetadataClient(dsn="postgresql+psycopg2://u:p@host/db", conn_factory=factory)
    client.start_run("sales_orders_pipeline", task_name="extract")

    assert seen == ["postgresql://u:p@host/db"]


def test_start_run_inserts_and_returns_uuid():
    cur = FakeCursor()
    client = make_client(cur)

    run_id = client.start_run("sales_orders_pipeline", task_name="extract")

    assert isinstance(run_id, uuid.UUID)
    assert len(cur.executed) == 1
    sql, params = cur.executed[0]
    assert "INSERT INTO quarry_metadata.pipeline_runs" in sql
    assert params[0] == str(run_id)
    assert params[1] == "sales_orders_pipeline"
    assert params[2] == "extract"


def test_complete_run_rejects_non_terminal_status():
    cur = FakeCursor()
    client = make_client(cur)
    with pytest.raises(MetadataClientError):
        client.complete_run(uuid.uuid4(), status="running")


def test_complete_run_writes_terminal_status():
    cur = FakeCursor()
    client = make_client(cur)
    run_id = uuid.uuid4()

    client.complete_run(run_id, status="success", row_count=42)

    sql, params = cur.executed[0]
    assert "UPDATE quarry_metadata.pipeline_runs" in sql
    assert params[0] == "success"
    assert params[2] == 42
    assert params[4] == str(run_id)


def test_run_context_manager_success_path():
    cur = FakeCursor()
    client = make_client(cur)

    with client.run("sales_orders_pipeline", task_name="clean") as set_row_count:
        set_row_count(17)

    insert_sql, _ = cur.executed[0]
    update_sql, update_params = cur.executed[1]
    assert "INSERT INTO quarry_metadata.pipeline_runs" in insert_sql
    assert "UPDATE quarry_metadata.pipeline_runs" in update_sql
    assert update_params[0] == "success"
    assert update_params[2] == 17


def test_run_context_manager_failure_path_marks_failed_and_reraises():
    cur = FakeCursor()
    client = make_client(cur)

    with pytest.raises(ValueError):
        with client.run("sales_orders_pipeline", task_name="dq_gate"):
            raise ValueError("null-rate threshold exceeded")

    update_sql, update_params = cur.executed[1]
    assert "UPDATE quarry_metadata.pipeline_runs" in update_sql
    assert update_params[0] == "failed"
    assert "null-rate threshold exceeded" in update_params[3]


def test_get_runs_maps_rows_to_pipeline_run_objects():
    run_id = uuid.uuid4()
    row = {
        "run_id": run_id,
        "pipeline_name": "sales_orders_pipeline",
        "task_name": "extract",
        "dag_run_id": "manual__2026-07-13",
        "status": "success",
        "started_at": "2026-07-13T00:00:00Z",
        "ended_at": "2026-07-13T00:01:00Z",
        "row_count": 25,
        "error_message": None,
        "extra": {},
    }
    cur = FakeCursor(fetchall_result=[row])
    client = make_client(cur)

    runs = client.get_runs("sales_orders_pipeline")

    assert len(runs) == 1
    assert runs[0].run_id == run_id
    assert runs[0].row_count == 25


def test_register_dataset_upserts():
    cur = FakeCursor()
    client = make_client(cur)

    client.register_dataset(
        dataset_name="curated.sales_orders",
        zone="curated",
        location="s3://quarry-dev-curated-zone/sales_orders/",
        owner_role="T4-DE1",
        description="Curated sales orders, partitioned by order_date",
    )

    sql, params = cur.executed[0]
    assert "INSERT INTO quarry_metadata.dataset_catalog" in sql
    assert params[0] == "curated.sales_orders"


def test_list_catalog_maps_rows():
    row = {
        "dataset_name": "curated.sales_orders",
        "zone": "curated",
        "location": "s3://quarry-dev-curated-zone/sales_orders/",
        "owner_role": "T4-DE1",
        "description": None,
        "last_updated_at": None,
        "created_at": "2026-07-13T00:00:00Z",
    }
    cur = FakeCursor(fetchall_result=[row])
    client = make_client(cur)

    catalog = client.list_catalog()

    assert len(catalog) == 1
    assert catalog[0].dataset_name == "curated.sales_orders"


def test_watermark_round_trip_uses_expected_sql():
    cur = FakeCursor(fetchone_result={"watermark_value": "2026-07-12"})
    client = make_client(cur)

    value = client.get_watermark("sales_orders_pipeline", "sales_orders")
    assert value == "2026-07-12"

    client.set_watermark("sales_orders_pipeline", "sales_orders", "2026-07-13")
    sql, params = cur.executed[-1]
    assert "INSERT INTO quarry_metadata.watermarks" in sql
    assert params[2] == "2026-07-13"
