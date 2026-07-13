"""Database engine/session wiring for the metadata-api service.

Reads the same `quarry_metadata` schema written by
libs/metadata_client/schema.sql and libs/metadata_client/client.py — this
service is the read-side HTTP API over that store (BRD: "metadata/status
API platform service").
"""
from __future__ import annotations

import os
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DEFAULT_DATABASE_URL = (
    "postgresql+psycopg2://quarry_admin:quarry_dev_password@localhost:5432/quarry_metadata"
)

DATABASE_URL = os.environ.get("METADATA_DATABASE_URL", DEFAULT_DATABASE_URL)

# SQLite (used by the test suite) has no concept of the `quarry_metadata`
# Postgres schema. schema_translate_map lets the same ORM models declared
# with schema="quarry_metadata" run against SQLite by translating that
# schema name to the default (None) schema at execution time, and is a
# no-op against real Postgres.
_engine_kwargs: dict = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs = {"connect_args": {"check_same_thread": False}}

engine = create_engine(DATABASE_URL, **_engine_kwargs)
if DATABASE_URL.startswith("sqlite"):
    engine = engine.execution_options(schema_translate_map={"quarry_metadata": None})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
