from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import DatasetCatalogEntry, PipelineRun  # noqa: E402


@pytest.fixture()
def db_session():
    # StaticPool keeps a single shared connection alive for the whole engine
    # (instead of one per thread), which is required for an in-memory
    # SQLite DB here: FastAPI executes sync path operations in a threadpool
    # worker thread (starlette.concurrency.run_in_threadpool), which is a
    # different thread than the one that ran Base.metadata.create_all()
    # below. Without StaticPool, that worker thread would get a fresh,
    # empty `:memory:` database and every query would 404/error with
    # "no such table".
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    engine = engine.execution_options(schema_translate_map={"quarry_metadata": None})
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session):
    from fastapi.testclient import TestClient

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_client(client, db_session):
    now = datetime.now(timezone.utc)

    db_session.add_all(
        [
            PipelineRun(
                run_id="11111111-1111-1111-1111-111111111111",
                pipeline_name="sales_orders_pipeline",
                task_name="extract",
                dag_run_id="manual__2026-07-13T00:00:00+00:00",
                status="success",
                started_at=now - timedelta(minutes=10),
                ended_at=now - timedelta(minutes=9),
                row_count=27,
                error_message=None,
                extra={},
            ),
            PipelineRun(
                run_id="22222222-2222-2222-2222-222222222222",
                pipeline_name="sales_orders_pipeline",
                task_name="dq_gate",
                dag_run_id="manual__2026-07-13T00:00:00+00:00",
                status="failed",
                started_at=now - timedelta(minutes=8),
                ended_at=now - timedelta(minutes=7),
                row_count=None,
                error_message="null-rate threshold exceeded",
                extra={},
            ),
        ]
    )
    db_session.add(
        DatasetCatalogEntry(
            dataset_name="curated.sales_orders",
            zone="curated",
            location="s3://quarry-dev-curated-zone/sales_orders/",
            owner_role="T4-DE1",
            description="Curated, deduplicated sales_orders.",
            last_updated_at=now,
            created_at=now - timedelta(days=1),
        )
    )
    db_session.commit()
    return client
