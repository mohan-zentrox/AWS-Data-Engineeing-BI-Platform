from __future__ import annotations


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_get_pipeline_runs_returns_history_ordered_newest_first(seeded_client):
    resp = seeded_client.get("/pipelines/sales_orders_pipeline/runs")
    assert resp.status_code == 200

    body = resp.json()
    assert body["pipeline_name"] == "sales_orders_pipeline"
    assert body["run_count"] == 2
    # dq_gate started later than extract, so it should come first (desc order).
    assert body["runs"][0]["task_name"] == "dq_gate"
    assert body["runs"][0]["status"] == "failed"
    assert body["runs"][1]["task_name"] == "extract"
    assert body["runs"][1]["row_count"] == 27


def test_get_pipeline_runs_for_unknown_pipeline_returns_empty_list(seeded_client):
    resp = seeded_client.get("/pipelines/does_not_exist/runs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_count"] == 0
    assert body["runs"] == []


def test_get_pipeline_runs_respects_limit(seeded_client):
    resp = seeded_client.get("/pipelines/sales_orders_pipeline/runs", params={"limit": 1})
    assert resp.status_code == 200
    assert resp.json()["run_count"] == 1


def test_get_pipeline_runs_rejects_invalid_limit(seeded_client):
    resp = seeded_client.get("/pipelines/sales_orders_pipeline/runs", params={"limit": 0})
    assert resp.status_code == 422


def test_pipeline_run_out_accepts_uuid_run_id():
    """Postgres hands back a uuid.UUID for a UUID column; SQLite gives a str.

    This service is tested against SQLite but deployed against Postgres, so
    assert the response schema tolerates both. Without this, GET
    /pipelines/{name}/runs returns 500 against a real metadata store while the
    whole SQLite suite stays green.
    """
    import uuid as uuid_module
    from datetime import datetime, timezone

    from app.schemas import PipelineRunOut

    run_id = uuid_module.uuid4()

    class Row:
        pass

    row = Row()
    row.run_id = run_id
    row.pipeline_name = "sales_orders_pipeline"
    row.task_name = "extract"
    row.dag_run_id = "manual__1"
    row.status = "success"
    row.started_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
    row.ended_at = None
    row.row_count = 26
    row.error_message = None
    row.extra = None

    out = PipelineRunOut.model_validate(row)
    assert out.run_id == str(run_id)
    assert isinstance(out.run_id, str)


def test_run_id_column_uses_native_uuid_on_postgres():
    """The ORM column must ask Postgres for a string, not a uuid.UUID."""
    from app.models import PipelineRun
    from sqlalchemy import String
    from sqlalchemy.dialects import postgresql, sqlite

    col = PipelineRun.__table__.c.run_id
    # as_uuid=False is the part that matters: it is what makes the Postgres
    # read path yield str instead of uuid.UUID.
    assert col.type.dialect_impl(postgresql.dialect()).as_uuid is False
    # SQLite keeps the portable String variant so the test suite still works.
    assert isinstance(col.type.dialect_impl(sqlite.dialect()), String)
