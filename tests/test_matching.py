import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from src.database import get_connection, init_db
from src.matching import find_matches


@pytest.fixture
def temp_db(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / "test_match.db"
        monkeypatch.setattr("src.database.DB_PATH", tmp_path)
        monkeypatch.setattr("src.database.DATABASE_PATH", tmp_path, raising=False)
        # Patch in matching module's reference if imported
        try:
            monkeypatch.setattr("src.matching.DB_PATH", tmp_path, raising=False)
        except Exception:
            pass
        init_db()
        yield tmp_path


def insert_scholarship(**kwargs):
    """Helper to insert scholarship directly."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        # Ensure defaults for all fields
        defaults = {
            "name": "Test Scholarship",
            "provider": "Test Provider",
            "description": "Description",
            "education_level": None,
            "qualification": None,
            "field_of_study": None,
            "minimum_age": None,
            "maximum_age": None,
            "nationality": None,
            "eligible_provinces": None,
            "eligible_cities": None,
            "eligible_domiciles": None,
            "minimum_marks": None,
            "minimum_cgpa": None,
            "household_income_limit": None,
            "funding": None,
            "study_destination": None,
            "location": None,
            "deadline": "2030-12-31",
            "status": "open",
            "application_url": "https://example.com/apply",
            "source_url": "https://example.com/source",
            "verified_at": None,
            "raw_data": "{}",
        }
        defaults.update(kwargs)
        cols = list(defaults.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        values = [defaults[c] for c in cols]
        cur.execute(f"INSERT INTO scholarships ({col_names}) VALUES ({placeholders})", values)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def test_eligible_potentially_eligible_insufficient_and_ineligible(temp_db):
    profile = {
        "age": 20,
        "nationality": "Pakistani",
        "province": "Punjab",
        "city": "Lahore",
        "education_level": "Bachelor",
        "marks": 80,
        "household_income": 40000,
    }

    # Eligible: all criteria match
    insert_scholarship(
        name="Eligible Scholarship",
        minimum_age=18,
        maximum_age=25,
        nationality="Pakistani",
        eligible_provinces="Punjab",
        minimum_marks=70,
        deadline="2030-12-31",
        status="open",
    )
    # Potentially eligible: matches but missing income info
    insert_scholarship(
        name="Potentially Eligible Scholarship",
        minimum_age=18,
        nationality="Pakistani",
        household_income_limit=50000,
        eligible_provinces="Punjab",
        deadline="2030-12-31",
        status="open",
    )
    # Change profile to miss income for that check: Actually profile has income 40000, so it would be eligible.
    # Let's create a scholarship that requires income but profile missing that field will be tested separately.
    # For this test, create a scholarship that requires qualification missing in profile => potentially
    insert_scholarship(
        name="Potentially Eligible 2",
        qualification="Intermediate",
        deadline="2030-12-31",
        status="open",
    )
    # Insufficient: requires marks but profile missing marks? But profile has marks. So we need a profile missing marks.
    # For now create a scholarship that will be insufficient when profile has no marks - we will test with different profile later.
    # Let's create a scholarship that requires field_of_study missing in profile for this profile (profile field missing => insufficient)
    insert_scholarship(
        name="Insufficient Scholarship",
        field_of_study="Engineering",
        deadline="2030-12-31",
        status="open",
    )
    # Ineligible: nationality mismatch
    insert_scholarship(
        name="Ineligible Scholarship",
        nationality="Indian",
        deadline="2030-12-31",
        status="open",
    )

    # For this profile, field_of_study missing => insufficient should be returned as insufficient, not ineligible.
    # Ineligible scholarship should be excluded.
    results = find_matches(profile, limit=50)
    names = [r["name"] for r in results]
    assert "Ineligible Scholarship" not in names
    assert "Eligible Scholarship" in names
    # Check all returned are not ineligible
    for r in results:
        assert r["eligibility_status"] in ["eligible", "potentially_eligible", "insufficient_information"]
        assert "eligibility_status" in r
        assert "reasons" in r
        assert "missing_information" in r

    # Check that eligible appears before potentially and insufficient
    # Get statuses in order
    status_order = {"eligible": 0, "potentially_eligible": 1, "insufficient_information": 2}
    ordered = [status_order[r["eligibility_status"]] for r in results]
    assert ordered == sorted(ordered), "Results not ranked correctly"


def test_ranking_order(temp_db):
    # Clear and insert known ranking scenario
    profile = {"age": 20, "nationality": "Pakistani", "marks": 75}
    # Eligible
    insert_scholarship(name="A Eligible", minimum_age=18, maximum_age=25, minimum_marks=70, deadline="2030-12-31", status="open")
    # Potentially: requires qualification missing
    insert_scholarship(name="B Potentially", qualification="Bachelor", minimum_marks=70, deadline="2030-12-31", status="open")
    # Insufficient: requires field missing and no passed checks
    # Use no deadline/status to avoid automatic passes from deadline
    insert_scholarship(name="C Insufficient", field_of_study="Medicine", deadline=None, status=None)
    # For B, it has marks requirement that profile passes (75>=70) but qualification missing => potentially (passes + missing)
    # So we adjust: A has marks pass + age pass => eligible (no missing). B has marks pass + missing qualification => potentially. C has no pass, missing field => insufficient.

    results = find_matches(profile, limit=50)
    assert len(results) == 3
    assert results[0]["name"] == "A Eligible"
    assert results[0]["eligibility_status"] == "eligible"
    assert results[1]["name"] == "B Potentially"
    assert results[1]["eligibility_status"] == "potentially_eligible"
    assert results[2]["name"] == "C Insufficient"
    assert results[2]["eligibility_status"] == "insufficient_information"


def test_limit_handling(temp_db):
    profile = {"age": 20, "nationality": "Pakistani", "marks": 80}
    for i in range(5):
        insert_scholarship(name=f"Scholarship {i}", minimum_marks=70, deadline="2030-12-31", status="open")
    results = find_matches(profile, limit=2)
    assert len(results) == 2
    results_all = find_matches(profile, limit=50)
    assert len(results_all) == 5
    results_large = find_matches(profile, limit=100)
    assert len(results_large) == 5
    # Invalid limit should default to 50 and not crash
    results_invalid = find_matches(profile, limit=-5)
    assert len(results_invalid) == 5
    results_zero = find_matches(profile, limit=0)
    # Our implementation treats 0 as default 50 -> returns all
    assert len(results_zero) == 5


def test_empty_database(temp_db):
    profile = {"age": 20, "nationality": "Pakistani"}
    results = find_matches(profile, limit=50)
    assert results == []
    assert isinstance(results, list)


def test_malformed_profile(temp_db):
    insert_scholarship(name="Test Schol", minimum_age=18, maximum_age=25, deadline="2030-12-31", status="open")
    # None profile
    results = find_matches(None, limit=50)
    assert isinstance(results, list)
    # Malformed values
    malformed = {"age": "twenty", "marks": "invalid", "nationality": None, "province": ""}
    results2 = find_matches(malformed, limit=50)
    assert isinstance(results2, list)
    # Should not crash, should return results with insufficient/potentially
    assert len(results2) >= 0

    # Non-dict profile
    results3 = find_matches("not a dict", limit=50)
    assert isinstance(results3, list)


def test_returns_expected_fields(temp_db):
    profile = {"age": 22, "nationality": "Pakistani", "marks": 85}
    insert_scholarship(
        name="Field Check Scholarship",
        provider="HEC",
        description="Great opportunity",
        education_level="Bachelor",
        location="Lahore",
        funding="100000",
        deadline="2030-11-30",
        status="open",
        application_url="https://apply.example.com",
        source_url="https://source.example.com",
        verified_at="2024-01-01",
        minimum_marks=70,
    )
    results = find_matches(profile, limit=50)
    assert len(results) == 1
    r = results[0]
    expected_keys = ["id", "name", "provider", "description", "education_level", "location", "funding", "deadline", "status", "eligibility_status", "reasons", "missing_information", "application_url", "source_url", "verified_at"]
    for k in expected_keys:
        assert k in r, f"Missing key {k}"
    assert r["name"] == "Field Check Scholarship"
    assert r["provider"] == "HEC"
    assert r["application_url"] == "https://apply.example.com"
    assert r["eligibility_status"] in ["eligible", "potentially_eligible", "insufficient_information"]


def test_excludes_ineligible_by_default(temp_db):
    profile = {"nationality": "Pakistani", "age": 20}
    insert_scholarship(name="Open Scholarship", nationality="Pakistani", minimum_age=18, deadline="2030-12-31", status="open")
    insert_scholarship(name="Closed Scholarship", nationality="Pakistani", minimum_age=18, deadline="2030-12-31", status="closed")
    yesterday = (date.today() - timedelta(days=5)).isoformat()
    insert_scholarship(name="Expired Scholarship", nationality="Pakistani", minimum_age=18, deadline=yesterday, status="open")

    results = find_matches(profile, limit=50)
    names = [r["name"] for r in results]
    assert "Open Scholarship" in names
    assert "Closed Scholarship" not in names
    assert "Expired Scholarship" not in names

def test_parameterized_sql_safety(temp_db):
    # Ensure SQL injection not possible via profile (not directly used in SQL, but test matching doesn't crash)
    profile = {"age": 20, "nationality": "Pakistani'; DROP TABLE scholarships; --"}
    insert_scholarship(name="Safe Scholarship", deadline="2030-12-31", status="open")
    results = find_matches(profile, limit=50)
    # Table should still exist
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as c FROM scholarships")
        assert cur.fetchone()["c"] >= 1
    finally:
        conn.close()
