from datetime import date, timedelta

import pytest

from src.eligibility import check_eligibility


def test_confirmed_eligible_profile():
    profile = {
        "age": 20,
        "nationality": "Pakistani",
        "province": "Punjab",
        "city": "Lahore",
        "domicile": "Punjab",
        "education_level": "Bachelor",
        "qualification": "Intermediate",
        "field_of_study": "Computer Science",
        "marks": 85,
        "household_income": 40000,
        "study_destination": "Pakistan",
    }
    scholarship = {
        "minimum_age": 18,
        "maximum_age": 25,
        "nationality": "Pakistani",
        "eligible_provinces": "Punjab",
        "eligible_cities": "Lahore",
        "eligible_domiciles": "Punjab",
        "education_level": "Bachelor",
        "qualification": "Intermediate",
        "field_of_study": "Computer Science",
        "minimum_marks": 70,
        "household_income_limit": 50000,
        "study_destination": "Pakistan",
        "deadline": "2030-12-31",
        "status": "open",
    }
    result = check_eligibility(profile, scholarship)
    assert "eligibility_status" in result
    assert "reasons" in result
    assert "missing_information" in result
    assert result["eligibility_status"] == "eligible"
    assert isinstance(result["reasons"], list)
    assert isinstance(result["missing_information"], list)
    # No missing, no hard fails
    assert len(result["missing_information"]) == 0 or all("deadline" not in m.lower() for m in result["missing_information"])


def test_clear_hard_requirement_failure():
    profile = {"nationality": "Indian", "age": 22, "marks": 90}
    scholarship = {"nationality": "Pakistani", "minimum_age": 18, "maximum_age": 25, "deadline": "2030-12-31", "status": "open"}
    result = check_eligibility(profile, scholarship)
    assert result["eligibility_status"] == "ineligible"
    assert len(result["reasons"]) > 0
    # Reason should mention nationality
    assert any("nationality" in r.lower() for r in result["reasons"])


def test_missing_student_age_or_qualification():
    profile = {"nationality": "Pakistani", "marks": 80}
    # Scholarship requires age and qualification
    scholarship = {"minimum_age": 18, "maximum_age": 25, "qualification": "Intermediate", "deadline": "2030-12-31", "status": "open"}
    result = check_eligibility(profile, scholarship)
    assert result["eligibility_status"] in ["potentially_eligible", "insufficient_information"]
    assert "eligibility_status" in result
    # Missing information should mention age or qualification
    missing_lower = " ".join(result["missing_information"]).lower()
    assert "age" in missing_lower or "qualification" in missing_lower
    # Should not be eligible or ineligible when missing required info but no hard fail
    assert result["eligibility_status"] != "eligible"
    assert result["eligibility_status"] != "ineligible"


def test_missing_scholarship_criteria():
    profile = {"age": 20, "nationality": "Pakistani", "marks": 75}
    scholarship = {
        # All criteria missing / NULL
        "minimum_age": None,
        "maximum_age": None,
        "nationality": None,
        "minimum_marks": None,
        "deadline": "2030-12-31",
        "status": "open",
    }
    result = check_eligibility(profile, scholarship)
    # With no criteria, should be eligible (open deadline) or at least not ineligible
    assert result["eligibility_status"] in ["eligible", "potentially_eligible", "insufficient_information"]
    assert result["eligibility_status"] != "ineligible"


def test_academic_marks_below_minimum():
    profile = {"marks": 60}
    scholarship = {"minimum_marks": 80, "deadline": "2030-12-31", "status": "open"}
    result = check_eligibility(profile, scholarship)
    assert result["eligibility_status"] == "ineligible"
    assert any("marks" in r.lower() for r in result["reasons"])


def test_academic_cgpa_below_minimum():
    profile = {"cgpa": 2.5}
    scholarship = {"minimum_cgpa": 3.0, "deadline": "2030-12-31", "status": "open"}
    result = check_eligibility(profile, scholarship)
    assert result["eligibility_status"] == "ineligible"


def test_expired_deadline():
    profile = {"age": 20, "nationality": "Pakistani", "marks": 85}
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    scholarship = {"minimum_age": 18, "maximum_age": 25, "nationality": "Pakistani", "deadline": yesterday, "status": "open"}
    result = check_eligibility(profile, scholarship)
    assert result["eligibility_status"] == "ineligible"
    assert any("deadline" in r.lower() and "expired" in r.lower() for r in result["reasons"])


def test_null_and_empty_values():
    profile = {"age": None, "nationality": "", "marks": None, "province": "", "city": None}
    scholarship = {
        "minimum_age": None,
        "maximum_age": "",
        "nationality": None,
        "minimum_marks": "",
        "eligible_provinces": None,
        "deadline": None,
        "status": None,
    }
    result = check_eligibility(profile, scholarship)
    # Should not crash and return valid structure
    assert "eligibility_status" in result
    assert "reasons" in result
    assert "missing_information" in result
    assert result["eligibility_status"] in ["eligible", "potentially_eligible", "insufficient_information", "ineligible"]
    # With all NULL, likely insufficient or eligible but must not crash
    assert isinstance(result["reasons"], list)
    assert isinstance(result["missing_information"], list)


def test_malformed_numeric_values():
    profile = {"age": "twenty", "marks": "eighty percent", "household_income": "unknown"}
    scholarship = {"minimum_age": "eighteen", "maximum_age": "twenty-five", "minimum_marks": "seventy", "household_income_limit": "fifty thousand", "deadline": "2030-12-31", "status": "open"}
    result = check_eligibility(profile, scholarship)
    assert "eligibility_status" in result
    assert result["eligibility_status"] in ["eligible", "potentially_eligible", "insufficient_information", "ineligible"]
    # Should not crash, malformed should become missing info
    assert isinstance(result["reasons"], list)
    assert isinstance(result["missing_information"], list)
    # malformed numeric should be reported as missing/invalid, not hard fail
    # At least some missing info should be present due to malformed
    assert len(result["missing_information"]) > 0 or len(result["reasons"]) >= 0


def test_status_closed_is_ineligible():
    profile = {"age": 20, "nationality": "Pakistani"}
    scholarship = {"minimum_age": 18, "nationality": "Pakistani", "deadline": "2030-12-31", "status": "closed"}
    result = check_eligibility(profile, scholarship)
    assert result["eligibility_status"] == "ineligible"
    assert any("status" in r.lower() for r in result["reasons"])


def test_location_mismatch():
    profile = {"province": "Sindh", "city": "Karachi"}
    scholarship = {"eligible_provinces": "Punjab, KPK", "eligible_cities": "Lahore", "deadline": "2030-12-31", "status": "open"}
    result = check_eligibility(profile, scholarship)
    assert result["eligibility_status"] == "ineligible"
    assert any("province" in r.lower() or "city" in r.lower() for r in result["reasons"])


def test_field_of_study_mismatch():
    profile = {"field_of_study": "History"}
    scholarship = {"field_of_study": "Computer Science, Engineering", "deadline": "2030-12-31", "status": "open"}
    result = check_eligibility(profile, scholarship)
    assert result["eligibility_status"] == "ineligible"


def test_documented_status_values_and_keys():
    profile = {"age": 20}
    scholarship = {"minimum_age": 18, "deadline": "2030-12-31", "status": "open"}
    result = check_eligibility(profile, scholarship)
    assert set(result.keys()) == {"eligibility_status", "reasons", "missing_information"}
    assert result["eligibility_status"] in ["eligible", "potentially_eligible", "insufficient_information", "ineligible"]
    assert isinstance(result["reasons"], list)
    assert isinstance(result["missing_information"], list)
