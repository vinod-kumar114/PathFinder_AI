"""Regression tests: schema migration, transactions and test isolation."""

import sqlite3

import pytest

import src.database as dbmod
from src.database import EXPECTED_COLUMNS, get_connection, get_db_path, init_db
from tests.conftest import REAL_DB


def columns():
    conn = sqlite3.connect(str(get_db_path()))
    try:
        return [r[1] for r in conn.execute("PRAGMA table_info(scholarships)").fetchall()]
    finally:
        conn.close()


def make_legacy_db(path):
    """An older database that only has some columns and already contains data."""
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE scholarships (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, "
                 "provider TEXT, deadline TEXT)")
    conn.executemany("INSERT INTO scholarships (name, provider, deadline) VALUES (?, ?, ?)", [
        ("Legacy One", "Old Org", "2030-01-01"),
        ("Legacy Two", None, None),
    ])
    conn.commit()
    conn.close()


def test_migration_preserves_existing_rows_and_adds_columns(db_path):
    make_legacy_db(db_path)
    init_db()
    assert set(EXPECTED_COLUMNS) <= set(columns())
    conn = get_connection()
    rows = [dict(r) for r in conn.execute("SELECT * FROM scholarships ORDER BY id")]
    conn.close()
    assert [(r["id"], r["name"], r["provider"], r["deadline"]) for r in rows] == [
        (1, "Legacy One", "Old Org", "2030-01-01"), (2, "Legacy Two", None, None)]
    assert all(r["raw_data"] is None and r["external_id"] is None for r in rows)


def test_migration_is_idempotent(db_path):
    make_legacy_db(db_path)
    init_db()
    cols_first = columns()
    init_db()
    assert columns() == cols_first
    conn = get_connection()
    assert conn.execute("SELECT COUNT(*) FROM scholarships").fetchone()[0] == 2
    conn.close()


def test_init_db_on_existing_current_db_keeps_data():
    init_db()
    conn = get_connection()
    conn.execute("INSERT INTO scholarships (name) VALUES ('Keep Me')")
    conn.commit()
    conn.close()
    init_db()
    conn = get_connection()
    assert [r[0] for r in conn.execute("SELECT name FROM scholarships")] == ["Keep Me"]
    conn.close()


def test_failed_migration_rolls_back_completely(db_path, monkeypatch):
    """If a later migration step fails, earlier ALTERs must not stay half-applied."""
    make_legacy_db(db_path)
    before = columns()
    monkeypatch.setattr(dbmod, "_INDEX_STATEMENTS", ("CREATE INDEX this is not valid sql",))
    with pytest.raises(RuntimeError, match="Database initialization failed"):
        init_db()
    assert columns() == before                     # no partial column additions
    conn = sqlite3.connect(str(db_path))
    assert conn.execute("SELECT COUNT(*) FROM scholarships").fetchone()[0] == 2   # data intact
    conn.close()


def test_table_without_id_is_refused_without_modification(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE scholarships (name TEXT)")
    conn.execute("INSERT INTO scholarships VALUES ('x')")
    conn.commit()
    conn.close()
    with pytest.raises(RuntimeError, match="no 'id' column"):
        init_db()
    assert columns() == ["name"]


def test_unwritable_database_path_raises_runtimeerror(tmp_path, monkeypatch):
    bad = tmp_path / "a_directory.db"
    bad.mkdir()
    monkeypatch.setattr(dbmod, "DB_PATH", bad)
    monkeypatch.setattr(dbmod, "DATABASE_PATH", bad)
    with pytest.raises(RuntimeError):
        init_db()


# ------------------------------------------------------------ test isolation
def test_tests_use_a_temporary_database(db_path):
    assert get_db_path() == db_path
    assert get_db_path() != REAL_DB
    assert "scholarships.db" != get_db_path().name or get_db_path().parent != REAL_DB.parent


def test_patching_only_legacy_alias_is_honoured_not_ignored(tmp_path, monkeypatch):
    """Old tests patched DATABASE_PATH only; that must never fall through to the real DB."""
    legacy = tmp_path / "legacy_alias.db"
    monkeypatch.setattr(dbmod, "DB_PATH", dbmod._DEFAULT_DB_PATH)
    monkeypatch.setattr(dbmod, "DATABASE_PATH", legacy)
    assert get_db_path() == legacy


def test_conflicting_path_overrides_are_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "a.db")
    monkeypatch.setattr(dbmod, "DATABASE_PATH", tmp_path / "b.db")
    with pytest.raises(RuntimeError, match="different locations"):
        get_connection()


def test_real_database_file_is_not_created_by_the_suite():
    init_db()
    # conftest compares the real DB before/after every test; additionally it must not appear
    # unless it already existed before this run.
    assert REAL_DB.exists() == dbmod_real_db_existed_at_import


dbmod_real_db_existed_at_import = REAL_DB.exists()
