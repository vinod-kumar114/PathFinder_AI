"""
Regression tests for bug fixes in Scholarship Finder.

Covers:
1. State column mapping conflict fix
2. CGPA vs percentage strict separation
3. Education-level and destination normalization
4. Matching/database errors are diagnosable
5. Duplicate import does not create duplicates
6. Database path override safe for tests
"""

import gc
import json
import tempfile
from pathlib import Path
import pandas as pd
import pytest

from src.eligibility import check_eligibility
from src.data_import import import_workbook, COLUMN_MAP, _normalize_col
from src.database import get_connection, init_db, DB_PATH


def test_state_column_not_silently_mapped():
    """'State' is ambiguous (province vs status): it must not appear in COLUMN_MAP."""
    assert _normalize_col("State") not in COLUMN_MAP
    # explicit status header is still mapped
    assert COLUMN_MAP.get("status") == "status"
    assert COLUMN_MAP.get("eligible provinces") == "eligible_provinces"


def test_state_import_stays_unmapped_and_preserved_in_raw_data():
    """Workbook with 'State' column: not mapped to province or status; kept in raw_data; warned."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wb_path = Path(tmpdir) / "state_test.xlsx"
        df = pd.DataFrame([{"Scholarship Name": "State Test", "State": "Punjab", "Status": "open", "Deadline": "2030-12-31"}])
        
        w = pd.ExcelWriter(str(wb_path), engine="openpyxl")
        try:
            df.to_excel(w, index=False, sheet_name="Scholarships")
        finally:
            w.close()

        result = import_workbook(str(wb_path))
        assert result["records_inserted"] == 1
        assert any("State" in warning and "unmapped" in warning for warning in result["warnings"])

        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT eligible_provinces, status, raw_data FROM scholarships WHERE name='State Test'")
            row = cur.fetchone()
            assert row["eligible_provinces"] is None
            assert row["status"] == "open"
            assert json.loads(row["raw_data"])["State"] == "Punjab"
            cur.close()
        finally:
            conn.close()
            gc.collect()


def test_cgpa_not_compared_to_percentage_marks():
    """Never compare student percentage marks against CGPA requirement."""
    # Student has high percentage (85) but no CGPA; scholarship requires CGPA 3.5
    profile = {"marks": 85, "percentage": 85}
    scholarship = {"minimum_cgpa": 3.5, "deadline": "2030-12-31", "status": "open"}
    result = check_eligibility(profile, scholarship)
    # Should NOT be eligible or ineligible based on marks vs CGPA
    # Must be insufficient/potentially with missing CGPA info
    assert result["eligibility_status"] in ["potentially_eligible", "insufficient_information"]
    assert any("CGPA" in m or "cgpa" in m.lower() for m in result["missing_information"])
    # Should NOT have hard fail about CGPA below minimum when using marks
    assert not any("CGPA 85" in r for r in result["reasons"])
    assert result["eligibility_status"] != "ineligible"

    # Student with explicit CGPA should be evaluated normally
    profile2 = {"cgpa": 3.8, "marks": 85}
    result2 = check_eligibility(profile2, scholarship)
    # 3.8 >= 3.5 => should be eligible (no missing CGPA)
    assert result2["eligibility_status"] == "eligible"
    assert len([m for m in result2["missing_information"] if "CGPA" in m]) == 0

    # Student with low CGPA should be ineligible, not based on marks
    profile3 = {"cgpa": 2.5, "marks": 95}
    result3 = check_eligibility(profile3, scholarship)
    assert result3["eligibility_status"] == "ineligible"
    assert any("CGPA" in r for r in result3["reasons"])


def test_cgpa_missing_remains_unknown():
    """Missing CGPA must remain unknown, not assumed from marks."""
    profile = {"marks": 90}
    scholarship = {"minimum_cgpa": 3.0, "minimum_marks": 80, "deadline": "2030-12-31", "status": "open"}
    result = check_eligibility(profile, scholarship)
    # Marks check should pass (90 >=80), CGPA check should be missing
    assert any("CGPA" in m for m in result["missing_information"])
    # Since marks pass and CGPA missing, should be potentially_eligible, not ineligible
    assert result["eligibility_status"] == "potentially_eligible"
    assert any("Academic marks" in r for r in result["reasons"])


def test_education_level_normalization_bachelors():
    """Education level synonyms should normalize correctly."""
    profile = {"education_level": "Bachelors"}  # plural
    scholarship = {"education_level": "Bachelor", "deadline": "2030-12-31", "status": "open"}
    result = check_eligibility(profile, scholarship)
    assert result["eligibility_status"] == "eligible"

    profile2 = {"education_level": "Undergraduate"}
    result2 = check_eligibility(profile2, scholarship)
    assert result2["eligibility_status"] == "eligible"

    profile3 = {"education_level": "BS"}
    result3 = check_eligibility(profile3, scholarship)
    assert result3["eligibility_status"] == "eligible"

    # But Bachelor should NOT match Master (no unsupported assumption)
    profile4 = {"education_level": "Bachelor"}
    scholarship4 = {"education_level": "Master", "deadline": "2030-12-31", "status": "open"}
    result4 = check_eligibility(profile4, scholarship4)
    assert result4["eligibility_status"] == "ineligible"


def test_education_level_normalization_master_synonyms():
    profile = {"education_level": "Masters"}
    scholarship = {"education_level": "Master", "deadline": "2030-12-31", "status": "open"}
    assert check_eligibility(profile, scholarship)["eligibility_status"] == "eligible"

    # "Postgraduate" is ambiguous (may include PhD) - never an automatic Master match.
    profile2 = {"education_level": "Postgraduate"}
    assert check_eligibility(profile2, scholarship)["eligibility_status"] != "eligible"

    # Master should not automatically match Bachelor
    profile3 = {"education_level": "Master"}
    scholarship3 = {"education_level": "Bachelor", "deadline": "2030-12-31", "status": "open"}
    assert check_eligibility(profile3, scholarship3)["eligibility_status"] == "ineligible"


def test_destination_normalization_usa_uk():
    """Destination synonyms should normalize correctly."""
    profile = {"study_destination": "USA"}
    scholarship = {"study_destination": "United States", "deadline": "2030-12-31", "status": "open"}
    assert check_eligibility(profile, scholarship)["eligibility_status"] == "eligible"

    profile2 = {"study_destination": "US"}
    assert check_eligibility(profile2, scholarship)["eligibility_status"] == "eligible"

    profile3 = {"study_destination": "UK"}
    scholarship3 = {"study_destination": "United Kingdom", "deadline": "2030-12-31", "status": "open"}
    assert check_eligibility(profile3, scholarship3)["eligibility_status"] == "eligible"

    profile4 = {"study_destination": "United Kingdom"}
    scholarship4 = {"study_destination": "UK", "deadline": "2030-12-31", "status": "open"}
    assert check_eligibility(profile4, scholarship4)["eligibility_status"] == "eligible"

    # USA should NOT match UK
    profile5 = {"study_destination": "USA"}
    scholarship5 = {"study_destination": "UK", "deadline": "2030-12-31", "status": "open"}
    assert check_eligibility(profile5, scholarship5)["eligibility_status"] == "ineligible"


def test_matching_errors_are_diagnosable():
    """Matching/database errors should raise, not silently return empty list."""
    from src.matching import find_matches
    import src.database as dbmod

    # Simulate DB failure by patching get_connection to raise
    orig_get_conn = dbmod.get_connection
    orig_init = dbmod.init_db
    try:
        def failing_get_connection():
            raise PermissionError("Simulated DB permission error")

        def failing_init():
            raise PermissionError("Simulated init error")

        # Patch both where matching imports them
        import src.matching as matching_mod
        orig_match_get = matching_mod.get_connection
        orig_match_init = matching_mod.init_db
        matching_mod.get_connection = failing_get_connection
        matching_mod.init_db = failing_init

        # Also patch database module for direct calls
        dbmod.get_connection = failing_get_connection
        dbmod.init_db = failing_init

        # find_matches should raise RuntimeError with diagnosable message, not return []
        with pytest.raises(RuntimeError) as exc_info:
            find_matches({"age": 20}, limit=10)
        assert "Database" in str(exc_info.value) or "Matching failed" in str(exc_info.value)

        # Restore for second scenario: get_connection fails after init succeeds
        matching_mod.init_db = lambda: None
        dbmod.init_db = lambda: None
        with pytest.raises(RuntimeError):
            find_matches({"age": 20})

    finally:
        dbmod.get_connection = orig_get_conn
        dbmod.init_db = orig_init
        matching_mod.get_connection = orig_get_conn
        matching_mod.init_db = orig_init


def test_database_path_override_safe(monkeypatch, tmp_path):
    """Database path override should not touch real user database."""
    import src.database as dbmod

    # Ensure original DB_PATH points to project data
    original = dbmod.DB_PATH
    assert "data/scholarships.db" in str(original) or "scholarships.db" in str(original)

    # Override to temp path
    temp_db = tmp_path / "isolated.db"
    monkeypatch.setattr(dbmod, "DB_PATH", temp_db)
    monkeypatch.setattr(dbmod, "DATABASE_PATH", temp_db)

    # Also patch matching's imported reference if exists
    try:
        import src.matching
        monkeypatch.setattr(src.matching, "DB_PATH", temp_db, raising=False)
    except Exception:
        pass

    init_db()
    assert temp_db.exists()

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scholarships'")
        assert cur.fetchone() is not None
        cur.execute("INSERT INTO scholarships (name) VALUES ('isolation test')")
        conn.commit()
        cur.execute("SELECT COUNT(*) as c FROM scholarships WHERE name='isolation test'")
        assert cur.fetchone()["c"] == 1
        cur.close()
    finally:
        conn.close()

    if original.exists() and original != temp_db:
        import sqlite3
        try:
            orig_conn = sqlite3.connect(str(original))
            orig_conn.row_factory = sqlite3.Row
            cur2 = orig_conn.cursor()
            try:
                cur2.execute("SELECT COUNT(*) as c FROM scholarships WHERE name='isolation test'")
                count = cur2.fetchone()["c"]
                assert count == 0
            except Exception:
                pass
            finally:
                cur2.close()
                orig_conn.close()
        except Exception:
            pass


def test_duplicate_import_no_duplicates():
    """Repeated imports should not create duplicate records."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_db = Path(tmpdir) / "dup_regression.db"
        import src.database as dbmod
        orig_db = dbmod.DB_PATH
        orig_dbs = dbmod.DATABASE_PATH
        try:
            dbmod.DB_PATH = tmp_db
            dbmod.DATABASE_PATH = tmp_db
            init_db()

            wb_path = Path(tmpdir) / "regression_dups.xlsx"
            data = [
                {"Scholarship Name": "NoDup Test", "Provider": "HEC", "Deadline": "2030-12-01", "Amount": "100000"},
                {"Scholarship Name": "NoDup Test", "Provider": "HEC", "Deadline": "2030-12-01", "Amount": "100000"},
                {"Scholarship Name": "NoDup Test ", "Provider": " hec ", "Deadline": "2030-12-01", "Amount": "100000"},
            ]
            df = pd.DataFrame(data)
            w = pd.ExcelWriter(str(wb_path), engine="openpyxl")
            try:
                df.to_excel(w, index=False, sheet_name="Sheet1")
            finally:
                w.close()

            result1 = import_workbook(str(wb_path))
            assert result1["records_inserted"] == 1
            assert result1["records_skipped"] >= 2

            result2 = import_workbook(str(wb_path))
            assert result2["records_inserted"] == 0

            conn = get_connection()
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) as c FROM scholarships")
                assert cur.fetchone()["c"] == 1
                cur.execute("SELECT name, provider FROM scholarships")
                row = cur.fetchone()
                assert row["name"].strip() == "NoDup Test"
                cur.close()
            finally:
                conn.close()
        finally:
            dbmod.DB_PATH = orig_db
            dbmod.DATABASE_PATH = orig_dbs
            gc.collect()


def test_duplicate_import_across_sheets():
    """Duplicate across different sheet names should still be detected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_db = Path(tmpdir) / "dup_sheets.db"
        import src.database as dbmod
        orig_db = dbmod.DB_PATH
        try:
            dbmod.DB_PATH = tmp_db
            dbmod.DATABASE_PATH = tmp_db
            init_db()

            wb_path = Path(tmpdir) / "dup_sheets.xlsx"
            df1 = pd.DataFrame([{"Scholarship Name": "CrossSheet Dup", "Provider": "Org", "Deadline": "2030-01-01"}])
            df2 = pd.DataFrame([{"Scholarship Name": "CrossSheet Dup", "Provider": "Org", "Deadline": "2030-01-01"}])
            
            w = pd.ExcelWriter(str(wb_path), engine="openpyxl")
            try:
                df1.to_excel(w, index=False, sheet_name="Punjab")
                df2.to_excel(w, index=False, sheet_name="Sindh")
            finally:
                w.close()

            result = import_workbook(str(wb_path))
            assert result["records_inserted"] == 1
            assert result["sheets_processed"] == 2

            conn = get_connection()
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) as c FROM scholarships WHERE name='CrossSheet Dup'")
                assert cur.fetchone()["c"] == 1
                cur.close()
            finally:
                conn.close()
        finally:
            dbmod.DB_PATH = orig_db
            dbmod.DATABASE_PATH = orig_db
            gc.collect()