import os
import sqlite3
import pytest
from src.database import init_db, seed_database_if_empty, get_connection

def test_verification_cache_table_creation(isolated_database):
    init_db()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='verification_cache'")
        row = cursor.fetchone()
        assert row is not None
    finally:
        conn.close()

def test_seed_database_if_empty_missing_file(isolated_database):
    init_db()
    res = seed_database_if_empty("non_existent_file.xlsx")
    assert res["seeded"] is False
    assert "not found" in res["reason"]
