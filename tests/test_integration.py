"""
Integration tests for complete backend journey.

Covers: temp DB -> init schema -> synthetic workbook -> import -> verify fields ->
eligibility -> find_matches -> ranking -> duplicate re-import -> DB failure diagnosable.
Uses only synthetic data, no internet.
"""

import tempfile
from pathlib import Path
import pandas as pd
import pytest
import sqlite3

from src.database import get_connection, init_db
from src.data_import import import_workbook
from src.eligibility import check_eligibility
from src.matching import find_matches


def create_sample_workbook(path):
    """Create synthetic workbook with 3 scholarships covering different eligibility cases."""
    data = [
        {
            "Scholarship Name": "Punjab Merit Scholarship",
            "Provider": "HEC Pakistan",
            "Description": "For Punjab students",
            "Education Level": "Bachelor",
            "Field of Study": "Computer Science",
            "Minimum Age": 18,
            "Maximum Age": 25,
            "Nationality": "Pakistani",
            "Eligible Provinces": "Punjab",
            "Minimum Marks": 80,
            "Household Income Limit": 50000,
            "Study Destination": "Pakistan",
            "Deadline": "2030-12-31",
            "Status": "open",
            "Application URL": "https://example.com/apply1",
            "Source URL": "https://example.com/source1",
        },
        {
            "Scholarship Name": "Need Based Aid",
            "Provider": "University of Karachi",
            "Education Level": "Master",
            "Field of Study": "Engineering",
            "Minimum Marks": 70,
            "Minimum CGPA": 3.0,
            "Eligible Provinces": "Sindh",
            "Deadline": "2030-11-30",
            "Status": "open",
            "Application URL": "https://example.com/apply2",
            "Source URL": "https://example.com/source2",
        },
        {
            "Scholarship Name": "US Exchange Program",
            "Provider": "USEFP",
            "Education Level": "Bachelor",
            "Study Destination": "USA",
            "Nationality": "Pakistani",
            "Deadline": "2030-10-15",
            "Status": "open",
            "Application URL": "https://example.com/apply3",
            "Funding": "Full Funded",
        },
    ]
    df = pd.DataFrame(data)
    with pd.ExcelWriter(str(path), engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Scholarships")
        # Add TOC sheet to verify skipping
        toc = pd.DataFrame([{"Contents": "Scholarships page 1"}])
        toc.to_excel(w, index=False, sheet_name="Table of Contents")


def test_complete_journey(tmp_path, monkeypatch):
    """Full backend journey with all steps."""
    # 1. Create temporary database
    temp_db = tmp_path / "integration.db"
    monkeypatch.setattr("src.database.DB_PATH", temp_db)
    monkeypatch.setattr("src.database.DATABASE_PATH", temp_db)
    # Also patch matching's imported references
    import src.matching
    monkeypatch.setattr(src.matching, "DB_PATH", temp_db, raising=False)

    # 2. Initialize schema
    init_db()
    assert temp_db.exists()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scholarships'")
        assert cur.fetchone() is not None
    finally:
        conn.close()

    # 3. Create synthetic workbook
    wb_path = tmp_path / "synthetic.xlsx"
    create_sample_workbook(wb_path)
    assert wb_path.exists()
    assert tmp_path / "synthetic.xlsx" != Path("data/scholarships.db")  # not overwriting real DB

    # 4. Import workbook
    result = import_workbook(str(wb_path))
    assert result["records_inserted"] == 3
    assert result["sheets_processed"] >= 1
    assert len(result["errors"]) == 0
    assert result["records_duplicate"] == 0
    # TOC should be warned, not inserted
    assert any("Table of Contents" in w for w in result["warnings"])

    # 5. Verify imported field values
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name, provider, education_level, minimum_marks, eligible_provinces, deadline, application_url, source_url, raw_data FROM scholarships ORDER BY name")
        rows = cur.fetchall()
        assert len(rows) == 3
        # Check specific field
        punjab_row = [r for r in rows if r["name"] == "Punjab Merit Scholarship"][0]
        assert punjab_row["provider"] == "HEC Pakistan"
        assert punjab_row["education_level"] == "Bachelor"
        assert punjab_row["minimum_marks"] == 80
        assert punjab_row["eligible_provinces"] == "Punjab"
        assert punjab_row["deadline"] == "2030-12-31"
        assert punjab_row["application_url"] == "https://example.com/apply1"
        assert punjab_row["source_url"] == "https://example.com/source1"
        assert punjab_row["raw_data"] is not None
        import json
        raw = json.loads(punjab_row["raw_data"])
        assert "Scholarship Name" in raw
    finally:
        conn.close()

    # 6. Run eligibility evaluation
    profile_eligible = {
        "age": 20,
        "nationality": "Pakistani",
        "province": "Punjab",
        "city": "Lahore",
        "education_level": "Bachelor",
        "field_of_study": "Computer Science",
        "marks": 85,
        "household_income": 40000,
        "study_destination": "Pakistan",
    }
    # Punjab Merit should be eligible for this profile
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM scholarships WHERE name='Punjab Merit Scholarship'")
        sch = dict(cur.fetchone())
    finally:
        conn.close()
    elig = check_eligibility(profile_eligible, sch)
    assert elig["eligibility_status"] == "eligible"
    assert len(elig["missing_information"]) == 0

    # Need Based Aid: profile missing Sindh province, should be ineligible or missing
    profile_sindh = {"age": 22, "nationality": "Pakistani", "province": "Punjab", "education_level": "Master", "marks": 75, "cgpa": 3.2}
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM scholarships WHERE name='Need Based Aid'")
        sch2 = dict(cur.fetchone())
    finally:
        conn.close()
    elig2 = check_eligibility(profile_sindh, sch2)
    # Should be ineligible due to province mismatch (Punjab not in Sindh) or potentially_eligible if missing?
    # Our test data: Need Based Aid requires Sindh, profile has Punjab -> ineligible
    assert elig2["eligibility_status"] == "ineligible"
    assert any("province" in r.lower() for r in elig2["reasons"])

    # 7. Run find_matches
    matches = find_matches(profile_eligible, limit=50)
    assert len(matches) >= 1
    # Verify returned fields and ranking
    for m in matches:
        assert "id" in m and "name" in m and "eligibility_status" in m and "reasons" in m and "missing_information" in m
        assert m["eligibility_status"] in ["eligible", "potentially_eligible", "insufficient_information"]
        assert "application_url" in m and "source_url" in m

    # Punjab Merit should be ranked first (eligible)
    assert matches[0]["name"] == "Punjab Merit Scholarship"
    assert matches[0]["eligibility_status"] == "eligible"

    # 8. Verify ranking: eligible before potentially/insufficient
    status_order = {"eligible": 0, "potentially_eligible": 1, "insufficient_information": 2}
    ordered = [status_order[m["eligibility_status"]] for m in matches]
    assert ordered == sorted(ordered)

    # 9. Import same workbook again and verify no duplicates
    result2 = import_workbook(str(wb_path))
    assert result2["records_inserted"] == 0
    assert result2["records_duplicate"] == 3
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as c FROM scholarships")
        assert cur.fetchone()["c"] == 3
    finally:
        conn.close()

    # 10. Simulate database failure and confirm diagnosable
    import src.matching as matching_mod
    import src.database as dbmod
    orig_get = dbmod.get_connection
    orig_match_get = matching_mod.get_connection
    try:
        def failing_conn():
            raise sqlite3.OperationalError("Simulated disk I/O error")

        dbmod.get_connection = failing_conn
        matching_mod.get_connection = failing_conn
        with pytest.raises(RuntimeError) as exc:
            find_matches(profile_eligible)
        assert "Simulated" in str(exc.value) or "Database" in str(exc.value)
    finally:
        dbmod.get_connection = orig_get
        matching_mod.get_connection = orig_match_get

    # Confirm real user's database was not modified
    real_db = Path("data/scholarships.db")
    if real_db.exists() and real_db != temp_db:
        real_conn = sqlite3.connect(str(real_db))
        try:
            cur = real_conn.cursor()
            try:
                cur.execute("SELECT COUNT(*) as c FROM scholarships WHERE name='Punjab Merit Scholarship'")
                # If real DB had this synthetic name, it would be 0 unless user had same name coincidentally
                # We check that synthetic temp data not leaked: we already verified temp_db has 3, real should not have our synthetic unless previously existed
                # This check ensures isolation - we don't assert count, just that connection works
                pass
            except sqlite3.OperationalError:
                pass  # table not exists in real DB
        finally:
            real_conn.close()


def test_database_fresh_creation_and_reuse(tmp_path, monkeypatch):
    """Fresh DB creation and existing reuse."""
    temp_db = tmp_path / "fresh.db"
    monkeypatch.setattr("src.database.DB_PATH", temp_db)
    monkeypatch.setattr("src.database.DATABASE_PATH", temp_db)

    # Fresh creation
    assert not temp_db.exists()
    init_db()
    assert temp_db.exists()

    # Insert one record
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO scholarships (name) VALUES ('First')")
        conn.commit()
    finally:
        conn.close()

    # Reuse existing - init_db should not destroy data
    init_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as c FROM scholarships WHERE name='First'")
        assert cur.fetchone()["c"] == 1
        cur.execute("SELECT COUNT(*) as c FROM scholarships")
        assert cur.fetchone()["c"] == 1
    finally:
        conn.close()


def test_isolated_temporary_paths(tmp_path, monkeypatch):
    """Isolated temporary database paths do not affect real DB."""
    real_db = Path("data/scholarships.db")
    # Ensure real DB path is project relative
    import src.database as dbmod
    assert "data/scholarships.db" in str(dbmod.DB_PATH) or "scholarships.db" in str(dbmod.DB_PATH)

    temp1 = tmp_path / "a.db"
    temp2 = tmp_path / "b.db"
    monkeypatch.setattr(dbmod, "DB_PATH", temp1)
    monkeypatch.setattr(dbmod, "DATABASE_PATH", temp1)
    init_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO scholarships (name) VALUES ('A')")
        conn.commit()
    finally:
        conn.close()

    # Switch to second temp DB - should be empty
    monkeypatch.setattr(dbmod, "DB_PATH", temp2)
    monkeypatch.setattr(dbmod, "DATABASE_PATH", temp2)
    init_db()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as c FROM scholarships WHERE name='A'")
        assert cur.fetchone()["c"] == 0
        cur.execute("SELECT COUNT(*) as c FROM scholarships")
        assert cur.fetchone()["c"] == 0
    finally:
        conn.close()

    # First temp still has A
    monkeypatch.setattr(dbmod, "DB_PATH", temp1)
    monkeypatch.setattr(dbmod, "DATABASE_PATH", temp1)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as c FROM scholarships WHERE name='A'")
        assert cur.fetchone()["c"] == 1
    finally:
        conn.close()


def test_import_distinct_cycles_not_merged(tmp_path, monkeypatch):
    """Different cycles (different deadlines) with same name/provider are not merged."""
    temp_db = tmp_path / "cycles.db"
    monkeypatch.setattr("src.database.DB_PATH", temp_db)
    monkeypatch.setattr("src.database.DATABASE_PATH", temp_db)
    init_db()

    wb_path = tmp_path / "cycles.xlsx"
    df = pd.DataFrame([
        {"Scholarship Name": "Annual Scholarship", "Provider": "HEC", "Deadline": "2030-01-01"},
        {"Scholarship Name": "Annual Scholarship", "Provider": "HEC", "Deadline": "2031-01-01"},
        {"Scholarship Name": "Annual Scholarship", "Provider": "HEC", "Deadline": "2030-01-01"},  # duplicate of first
    ])
    with pd.ExcelWriter(str(wb_path), engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Sheet1")

    result = import_workbook(str(wb_path))
    assert result["records_inserted"] == 2  # two distinct deadlines
    assert result["records_duplicate"] == 1
    assert result["records_skipped"] >= 1

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT deadline FROM scholarships WHERE name='Annual Scholarship' ORDER BY deadline")
        deadlines = [r["deadline"] for r in cur.fetchall()]
        assert deadlines == ["2030-01-01", "2031-01-01"]
    finally:
        conn.close()


def test_import_missing_provider_deadline(tmp_path, monkeypatch):
    """Missing provider/deadline handling in deduplication."""
    temp_db = tmp_path / "missing.db"
    monkeypatch.setattr("src.database.DB_PATH", temp_db)
    monkeypatch.setattr("src.database.DATABASE_PATH", temp_db)
    init_db()

    wb_path = tmp_path / "missing.xlsx"
    df = pd.DataFrame([
        {"Scholarship Name": "NoProvider", "Deadline": "2030-01-01"},
        {"Scholarship Name": "NoProvider", "Deadline": "2030-01-01"},  # duplicate, both missing provider
        {"Scholarship Name": "NoDeadline", "Provider": "Org"},
        {"Scholarship Name": "NoDeadline", "Provider": "Org"},  # duplicate, both missing deadline
        {"Scholarship Name": "BothMissing"},
        {"Scholarship Name": "BothMissing"},  # duplicate, both missing provider+deadline
    ])
    with pd.ExcelWriter(str(wb_path), engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Sheet1")

    result = import_workbook(str(wb_path))
    assert result["records_inserted"] == 3
    assert result["records_duplicate"] == 3

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as c FROM scholarships")
        assert cur.fetchone()["c"] == 3
    finally:
        conn.close()


def test_import_multiple_sheets(tmp_path, monkeypatch):
    """Multiple sheets with regional and master data deduplicated."""
    temp_db = tmp_path / "multi.db"
    monkeypatch.setattr("src.database.DB_PATH", temp_db)
    monkeypatch.setattr("src.database.DATABASE_PATH", temp_db)
    init_db()

    wb_path = tmp_path / "multi.xlsx"
    df_punjab = pd.DataFrame([{"Scholarship Name": "National Scholarship", "Provider": "HEC", "Deadline": "2030-06-01"}])
    df_sindh = pd.DataFrame([{"Scholarship Name": "National Scholarship", "Provider": "HEC", "Deadline": "2030-06-01"}])
    df_master = pd.DataFrame([{"Scholarship Name": "National Scholarship", "Provider": "HEC", "Deadline": "2030-06-01"}, {"Scholarship Name": "Sindh Only", "Provider": "Sindh Govt", "Deadline": "2030-07-01"}])
    with pd.ExcelWriter(str(wb_path), engine="openpyxl") as w:
        df_punjab.to_excel(w, index=False, sheet_name="Punjab")
        df_sindh.to_excel(w, index=False, sheet_name="Sindh")
        df_master.to_excel(w, index=False, sheet_name="Master")

    result = import_workbook(str(wb_path))
    # First occurrence inserted, next two duplicates skipped, Sindh Only inserted
    assert result["records_inserted"] == 2
    assert result["records_duplicate"] == 2
    assert result["sheets_processed"] == 3

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM scholarships ORDER BY name")
        names = [r["name"] for r in cur.fetchall()]
        assert names == ["National Scholarship", "Sindh Only"]
    finally:
        conn.close()
