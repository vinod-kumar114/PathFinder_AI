import pytest
from src.profile import normalize_profile, extract_profile_from_text, get_missing_profile_fields, summarize_profile

def test_normalize_profile_defaults():
    p = normalize_profile({})
    assert p["nationality"] == "Pakistani"
    assert p["study_destination"] == "Pakistan"
    assert p["age"] is None

def test_normalize_profile_aliases():
    p = normalize_profile({
        "age": "21 years",
        "province": "kpk",
        "education_level": "bachelors",
        "marks": "85.5",
        "cgpa": "3.8",
        "study_destination": "abroad and pakistan",
    })
    assert p["age"] == 21
    assert p["province"] == "Khyber Pakhtunkhwa"
    assert p["education_level"] == "Undergraduate / Bachelors"
    assert p["marks"] == 85.5
    assert p["cgpa"] == 3.8
    assert p["study_destination"] == "Both"

def test_extract_profile_from_text():
    text = "Hi, I am 22 years old from Punjab with 80% marks in FSC Pre-Engineering, looking for abroad scholarships."
    p = extract_profile_from_text(text)
    assert p["age"] == 22
    assert p["province"] == "Punjab"
    assert p["education_level"] == "Intermediate / A-Level"
    assert p["marks"] == 80.0
    assert p["study_destination"] == "Abroad"

def test_get_missing_profile_fields():
    p = {"age": 20, "province": "Punjab"}
    missing = get_missing_profile_fields(p)
    assert any("Education Level" in m for m in missing)
    assert any("Academic Grade" in m for m in missing)
    assert any("Field of Study" in m for m in missing)

def test_summarize_profile():
    p = {
        "education_level": "Undergraduate / Bachelors",
        "field_of_study": "Computer Science",
        "cgpa": 3.7,
        "province": "Punjab"
    }
    summary = summarize_profile(p)
    assert "Undergraduate / Bachelors" in summary
    assert "Computer Science" in summary
    assert "3.7" in summary
    assert "Punjab" in summary
