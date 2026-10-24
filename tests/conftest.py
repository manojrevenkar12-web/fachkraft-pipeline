from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from fkp import jobs as jobs_mod
from fkp.store import Store

T0 = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)  # a Monday, 10:00 in Berlin


@pytest.fixture(scope="session")
def demo_jobs() -> list[jobs_mod.Job]:
    return jobs_mod.load()


@pytest.fixture(scope="session")
def _db() -> Iterator[Store]:
    dsn = os.environ.get("FKP_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("FKP_TEST_DATABASE_URL not set")
    s = Store(dsn)
    with s.conn() as c:
        c.execute("DROP SCHEMA public CASCADE")
        c.execute("CREATE SCHEMA public")
    s.migrate()
    yield s
    s.close()


@pytest.fixture
def store(_db: Store, demo_jobs) -> Store:
    with _db.conn() as c:
        c.execute("TRUNCATE outbox, messages, events, conversations, jobs, suppression, erasures RESTART IDENTITY CASCADE")
    for j in demo_jobs:
        _db.upsert_job(j)
    return _db
