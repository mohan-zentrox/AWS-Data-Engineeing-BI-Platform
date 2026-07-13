from __future__ import annotations


def test_get_catalog_empty(client):
    resp = client.get("/catalog")
    assert resp.status_code == 200
    body = resp.json()
    assert body["dataset_count"] == 0
    assert body["datasets"] == []


def test_get_catalog_returns_registered_datasets(seeded_client):
    resp = seeded_client.get("/catalog")
    assert resp.status_code == 200

    body = resp.json()
    assert body["dataset_count"] == 1
    entry = body["datasets"][0]
    assert entry["dataset_name"] == "curated.sales_orders"
    assert entry["zone"] == "curated"
    assert entry["owner_role"] == "T4-DE1"
    assert entry["last_updated_at"] is not None
