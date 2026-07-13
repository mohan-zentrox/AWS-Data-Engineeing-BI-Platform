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
