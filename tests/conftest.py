"""
Shared test configuration.

Every test runs against a throw-away SQLite file. The autouse fixture below
redirects both DB_PATH and the legacy DATABASE_PATH alias, and after each test it
verifies that the project's real database (data/scholarships.db) was neither
created nor modified. A test that touches the real database therefore fails.
"""

import hashlib
from pathlib import Path

import pytest

import src.database as dbmod

REAL_DB = Path(dbmod.PROJECT_ROOT) / "data" / "scholarships.db"


def _snapshot(path):
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    """Point the application at a temporary database for every test."""
    before = _snapshot(REAL_DB)
    db = tmp_path / "test_scholarships.db"
    monkeypatch.setattr(dbmod, "DB_PATH", db)
    monkeypatch.setattr(dbmod, "DATABASE_PATH", db)
    assert dbmod.get_db_path() == db
    assert dbmod.get_db_path() != REAL_DB
    yield db
    assert _snapshot(REAL_DB) == before, "test modified the real database data/scholarships.db"


@pytest.fixture
def db_path(isolated_database):
    return isolated_database
