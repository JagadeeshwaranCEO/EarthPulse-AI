"""Shared test bootstrapping — in-memory SQLite, keyless, no WS broadcaster.

Defined once at the tests/ root so `engine.dispose()` runs exactly once at the
very end of the suite. Module-level tests must NOT dispose the engine mid-run:
test_scale switches scopes (chennai ↔ tamilnadu) against this shared DB, then
test_smoke continues on the restored chennai theatre.
"""

import os

os.environ["SEED_ON_BOOT"] = "false"
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ["WS_ENABLED"] = "false"

import pytest

from app.core.db import engine, init_db


@pytest.fixture(scope="session", autouse=True)
def boot():
    init_db()
    yield
    engine.dispose()
