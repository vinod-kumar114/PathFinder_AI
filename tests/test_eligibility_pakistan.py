"""Regression tests: eligibility with common Pakistani data variations.

Rule under test: a criterion fails only when both sides are clearly understood;
anything uncertain stays unknown and can never produce 'eligible'.
"""

from datetime import date, datetime

import pytest

from src.eligibility import check_eligibility

TODAY = date(2026, 10, 18)
FUTURE = "2031-06-15"


def run(profile, scholarship, today=TODAY):
    s = {"deadline": FUTURE, "status": "open"}
    s.update(scholarship)
    return check_eligibility(profile, s, today=today)


def status(profile, scholarship, today=TODAY):
    return run(profile, scholarship, today)["eligibility_status"]


NOT_ELIGIBLE_BUT_NOT_REJECTED = ("potentially_eligible", "insufficient_information")


# ----------------------------------------------------------------- nationality
@pytest.mark.parametrize("profile_nat", ["Pakistani", "pakistani", "Pakistan", "PK", "Pakistani National",
                                         "Pakistani citizen", "Pakistani, British"])
def test_pakistani_nationality_variants_match(profile_nat):
    assert status({"nationality": profile_nat}, {"nationality": "Pakistani"}) == "eligible"


@pytest.mark.parametrize("sch_nat", ["Pakistan", "Pakistani nationals", "PK", "Pakistani; Afghan"])
def test_scholarship_nationality_variants_match(sch_nat):
    assert status({"nationality": "Pakistani"}, {"nationality": sch_nat}) == "eligible"


def test_other_nationality_is_ineligible_for_pakistan_only():
    r = run({"nationality": "Indian"}, {"nationality": "Pakistani"})
    assert r["eligibility_status"] == "ineligible"


def test_overseas_pakistani_is_not_guessed():
    """'Overseas Pakistani' is a different category: unknown, never eligible and never rejected."""
    assert status({"nationality": "Overseas Pakistani"}, {"nationality": "Pakistani"}) in NOT_ELIGIBLE_BUT_NOT_REJECTED
    assert status({"nationality": "Pakistani"}, {"nationality": "Overseas Pakistani"}) in NOT_ELIGIBLE_BUT_NOT_REJECTED


def test_unrelated_nationalities_not_declared_ineligible_without_pakistan():
    """Neither side is Pakistani: we do not invent demonym/country equivalences."""
    assert status({"nationality": "Afghan"}, {"nationality": "Afghanistan"}) in NOT_ELIGIBLE_BUT_NOT_REJECTED


def test_all_nationalities_is_unrestricted_and_missing_profile_nationality_is_unknown():
    assert status({"nationality": "Pakistani"}, {"nationality": "All nationalities"}) == "eligible"
    r = run({}, {"nationality": "Pakistani"})
    assert r["eligibility_status"] == "insufficient_information"
    assert any("nationality" in m for m in r["missing_information"])


# ------------------------------------------------------------- education level
@pytest.mark.parametrize("profile_level,sch_level", [
    ("Intermediate (FSc)", "Intermediate"), ("FSc", "HSSC"), ("F.Sc.", "Intermediate"),
    ("A Level", "Intermediate"), ("BS", "Bachelors"), ("B.Sc", "Undergraduate"),
    ("MS", "Master"), ("M.Sc.", "Masters"), ("PhD", "Doctorate"), ("Matric", "SSC"),
    ("O Levels", "Matric"),
])
def test_education_level_equivalences(profile_level, sch_level):
    assert status({"education_level": profile_level}, {"education_level": sch_level}) == "eligible"


@pytest.mark.parametrize("profile_level", ["Postgraduate", "Graduate", "MPhil", "Associate Degree", "Diploma"])
def test_ambiguous_education_terms_are_never_matched_or_rejected(profile_level):
    """'Postgraduate'/'Graduate' etc. are deliberately NOT aliased to Master."""
    assert status({"education_level": profile_level}, {"education_level": "Master"}) in NOT_ELIGIBLE_BUT_NOT_REJECTED


def test_clearly_different_levels_are_ineligible():
    assert status({"education_level": "Bachelor"}, {"education_level": "Master"}) == "ineligible"
    assert status({"education_level": "Intermediate"}, {"education_level": "Bachelor"}) == "ineligible"


def test_education_list_with_one_unrecognised_item_is_unknown_not_ineligible():
    r = run({"education_level": "PhD"}, {"education_level": "MS / MPhil / Postdoc"})
    assert r["eligibility_status"] in NOT_ELIGIBLE_BUT_NOT_REJECTED


def test_education_list_match():
    assert status({"education_level": "BS"}, {"education_level": "Intermediate / undergrad"}) == "eligible"


# --------------------------------------------------------------- qualification
def test_qualification_equivalence_and_mismatch():
    assert status({"qualification": "FSc"}, {"qualification": "Intermediate"}) == "eligible"
    assert status({"qualification": "Matric"}, {"qualification": "Intermediate"}) == "ineligible"


def test_qualification_with_extra_text_is_unknown():
    assert status({"qualification": "FSc Pre-Medical"}, {"qualification": "FSc"}) in NOT_ELIGIBLE_BUT_NOT_REJECTED


# ------------------------------------------------------- marks / percentage
@pytest.mark.parametrize("marks", [75, 75.0, "75", "75%", "75 %", "850/1100"])
def test_percentage_forms_pass(marks):
    assert status({"marks": marks}, {"minimum_marks": 70}) == "eligible"


def test_percentage_below_minimum_is_ineligible():
    assert status({"marks": "65%"}, {"minimum_marks": 70}) == "ineligible"
    assert status({"marks": "700/1100"}, {"minimum_marks": 70}) == "ineligible"  # 63.6%


@pytest.mark.parametrize("marks", [3.5, "3.5", "3.5/4.0", "3.5 / 4"])
def test_gpa_like_value_in_marks_field_is_unknown_never_compared(marks):
    r = run({"marks": marks}, {"minimum_marks": 60})
    assert r["eligibility_status"] in NOT_ELIGIBLE_BUT_NOT_REJECTED
    assert any("GPA" in m for m in r["missing_information"])


@pytest.mark.parametrize("marks", [850, "First Division", "A-1", "abc"])
def test_unusable_marks_values_are_unknown(marks):
    assert status({"marks": marks}, {"minimum_marks": 60}) in NOT_ELIGIBLE_BUT_NOT_REJECTED


def test_scholarship_marks_that_look_like_cgpa_are_unknown():
    r = run({"marks": 90}, {"minimum_marks": 3.0})
    assert r["eligibility_status"] in NOT_ELIGIBLE_BUT_NOT_REJECTED


# --------------------------------------------------------------------- CGPA
@pytest.mark.parametrize("cgpa", [3.5, "3.5", "3.5/4.0", "3.5 out of 4"])
def test_cgpa_forms_pass(cgpa):
    assert status({"cgpa": cgpa}, {"minimum_cgpa": 3.0}) == "eligible"


def test_cgpa_below_minimum_is_ineligible():
    assert status({"cgpa": 2.5}, {"minimum_cgpa": 3.0}) == "ineligible"


def test_percentage_never_satisfies_cgpa_requirement():
    r = run({"marks": 95, "percentage": 95}, {"minimum_cgpa": 3.0})
    assert r["eligibility_status"] == "insufficient_information"
    assert any("CGPA" in m for m in r["missing_information"])


def test_cgpa_never_satisfies_percentage_requirement():
    r = run({"cgpa": 3.9}, {"minimum_marks": 60})
    assert r["eligibility_status"] == "insufficient_information"
    assert any("percentage" in m.lower() for m in r["missing_information"])


@pytest.mark.parametrize("cgpa", [85, "85%", "3.5/5", 4.5])
def test_cgpa_on_unclear_scale_is_unknown(cgpa):
    assert status({"cgpa": cgpa}, {"minimum_cgpa": 3.0}) in NOT_ELIGIBLE_BUT_NOT_REJECTED


def test_scholarship_cgpa_that_looks_like_percentage_is_unknown():
    assert status({"cgpa": 3.5}, {"minimum_cgpa": 70}) in NOT_ELIGIBLE_BUT_NOT_REJECTED


def test_both_marks_and_cgpa_required_each_checked_separately():
    r = run({"marks": 80, "cgpa": 2.0}, {"minimum_marks": 70, "minimum_cgpa": 3.0})
    assert r["eligibility_status"] == "ineligible"
    assert any("CGPA" in x for x in r["reasons"])


# --------------------------------------------------------------------- age
@pytest.mark.parametrize("age", [20, "20", "20 years"])
def test_age_forms(age):
    assert status({"age": age}, {"minimum_age": 18, "maximum_age": 25}) == "eligible"


def test_age_out_of_range_is_ineligible_and_garbage_is_unknown():
    assert status({"age": 30}, {"maximum_age": 25}) == "ineligible"
    assert status({"age": "twenty"}, {"maximum_age": 25}) in NOT_ELIGIBLE_BUT_NOT_REJECTED


# ------------------------------------------------------------------ geography
@pytest.mark.parametrize("profile_prov,sch_prov", [
    ("KPK", "Khyber Pakhtunkhwa"), ("KP", "Khyber Pakhtunkhwa"), ("Khyber-Pakhtunkhwa", "KPK"),
    ("Baluchistan", "Balochistan"), ("AJK", "Azad Jammu & Kashmir"), ("Azad Kashmir", "AJK"),
    ("GB", "Gilgit-Baltistan"), ("Islamabad", "ICT"), ("punjab", "Punjab"),
    ("Sindh", "Punjab, Sindh"),
])
def test_province_variants_match(profile_prov, sch_prov):
    assert status({"province": profile_prov}, {"eligible_provinces": sch_prov}) == "eligible"


def test_province_mismatch_is_ineligible():
    assert status({"province": "Punjab"}, {"eligible_provinces": "Sindh"}) == "ineligible"
    assert status({"province": "KPK"}, {"eligible_provinces": "Balochistan"}) == "ineligible"


def test_unrecognised_province_text_is_unknown_not_rejected():
    assert status({"province": "Southern Punjab"}, {"eligible_provinces": "Sindh"}) in NOT_ELIGIBLE_BUT_NOT_REJECTED


@pytest.mark.parametrize("sch_prov", ["All Pakistan", "All provinces", "Nationwide", "Pakistan"])
def test_unrestricted_province_values(sch_prov):
    assert status({"province": "Sindh"}, {"eligible_provinces": sch_prov}) == "eligible"


def test_domicile_is_not_inferred_from_province():
    r = run({"province": "Punjab"}, {"eligible_domiciles": "Punjab"})
    assert r["eligibility_status"] == "insufficient_information"
    assert any("domicile" in m for m in r["missing_information"])


def test_domicile_province_match_and_mismatch():
    assert status({"domicile": "KPK"}, {"eligible_domiciles": "Khyber Pakhtunkhwa"}) == "eligible"
    assert status({"domicile": "Punjab"}, {"eligible_domiciles": "Sindh"}) == "ineligible"


def test_district_domicile_vs_province_is_unknown():
    """District vs province hierarchy is not guessed."""
    assert status({"domicile": "Lahore"}, {"eligible_domiciles": "Punjab"}) in NOT_ELIGIBLE_BUT_NOT_REJECTED


def test_city_match_mismatch_missing():
    assert status({"city": "lahore"}, {"eligible_cities": "Lahore, Karachi"}) == "eligible"
    assert status({"city": "Quetta"}, {"eligible_cities": "Lahore, Karachi"}) == "ineligible"
    assert status({}, {"eligible_cities": "Lahore"}) == "insufficient_information"


@pytest.mark.parametrize("a,b,expected", [
    ("USA", "United States", "eligible"), ("UK", "United Kingdom", "eligible"),
    ("Turkiye", "Turkey", "eligible"), ("KSA", "Saudi Arabia", "eligible"),
    ("Italy", "France", "ineligible"), ("USA", "UK", "ineligible"),
])
def test_destination_matching(a, b, expected):
    assert status({"study_destination": a}, {"study_destination": b}) == expected


@pytest.mark.parametrize("a,b", [("England", "UK"), ("America", "USA"), ("Aus", "Australia"),
                                 ("Emirates", "UAE"), ("Britain", "United Kingdom")])
def test_risky_destination_aliases_are_not_invented(a, b):
    """England/America/Aus/Emirates/Britain are not treated as equal to the country."""
    assert status({"study_destination": a}, {"study_destination": b}) in NOT_ELIGIBLE_BUT_NOT_REJECTED


def test_region_destination_is_unknown():
    assert status({"study_destination": "Germany"}, {"study_destination": "Europe"}) in NOT_ELIGIBLE_BUT_NOT_REJECTED
    assert status({"study_destination": "Germany"}, {"study_destination": "Worldwide"}) == "eligible"


# --------------------------------------------------------------------- field
def test_field_exact_partial_and_different():
    assert status({"field_of_study": "Computer Science"}, {"field_of_study": "computer science"}) == "eligible"
    assert status({"field_of_study": "Mechanical Engineering"}, {"field_of_study": "Engineering"}) in NOT_ELIGIBLE_BUT_NOT_REJECTED
    assert status({"field_of_study": "Computer Science"}, {"field_of_study": "Science"}) in NOT_ELIGIBLE_BUT_NOT_REJECTED
    assert status({"field_of_study": "Law"}, {"field_of_study": "Medicine"}) == "ineligible"
    assert status({"field_of_study": "Law"}, {"field_of_study": "All fields"}) == "eligible"


# --------------------------------------------------------------------- income
def test_income_pkr_forms():
    assert status({"household_income": 40000}, {"household_income_limit": "Rs. 50,000"}) == "eligible"
    assert status({"household_income": 90000}, {"household_income_limit": "PKR 50,000/-"}) == "ineligible"


def test_income_period_mismatch_and_foreign_currency_are_unknown():
    assert status({"household_income": "40000 per month"}, {"household_income_limit": "600000 per annum"}) in NOT_ELIGIBLE_BUT_NOT_REJECTED
    assert status({"household_income": 40000}, {"household_income_limit": "50,000 per month"}) in NOT_ELIGIBLE_BUT_NOT_REJECTED
    assert status({"household_income": 40000}, {"household_income_limit": "USD 50,000"}) in NOT_ELIGIBLE_BUT_NOT_REJECTED
    assert status({"household_income": "40,000 per month"}, {"household_income_limit": "50,000 per month"}) == "eligible"


# --------------------------------------------------------------------- status
def test_closed_status_is_ineligible():
    assert status({"age": 20}, {"minimum_age": 18, "status": "Closed"}) == "ineligible"


@pytest.mark.parametrize("st", ["Upcoming", "Coming soon", "not_announced", "unknown", "Pending", "TBA"])
def test_non_open_statuses_are_never_eligible(st):
    r = run({"age": 20}, {"minimum_age": 18, "status": st})
    assert r["eligibility_status"] in NOT_ELIGIBLE_BUT_NOT_REJECTED
    assert any("status" in m for m in r["missing_information"])


@pytest.mark.parametrize("st", ["open", "OPEN", " Open ", "Active"])
def test_open_status_variants(st):
    assert status({"age": 20}, {"minimum_age": 18, "status": st}) == "eligible"


# ------------------------------------------------------------------- deadline
def test_deadline_today_is_still_open_and_yesterday_is_expired():
    assert status({"age": 20}, {"minimum_age": 18, "deadline": "2026-10-18"}) == "eligible"
    r = run({"age": 20}, {"minimum_age": 18, "deadline": "2026-10-17"})
    assert r["eligibility_status"] == "ineligible"
    assert any("expired" in x for x in r["reasons"])


@pytest.mark.parametrize("deadline", [
    "2031-06-15", "2031-06-15T23:59:00", "15/06/2031", "15-06-2031", "15.06.2031", "June 15, 2031",
    "15 June 2031", "15th June 2031", "15-Jun-2031", datetime(2031, 6, 15), date(2031, 6, 15),
])
def test_deadline_formats_parse(deadline):
    assert status({"age": 20}, {"minimum_age": 18, "deadline": deadline}) == "eligible"


@pytest.mark.parametrize("deadline", [
    "03/04/2031",                      # day/month order ambiguous
    "TBA", "Rolling", "Not announced", "2031",
    "2031-01-01 to 2031-03-01",        # opening and closing dates: which is the deadline?
    "Opens 01/01/2031, closes 31/03/2031",
    "2031-02-30",                      # impossible date
])
def test_ambiguous_or_unreadable_deadlines_stay_unknown(deadline):
    r = run({"age": 20}, {"minimum_age": 18, "deadline": deadline})
    assert r["eligibility_status"] == "potentially_eligible"
    assert any("deadline" in m for m in r["missing_information"])


def test_unambiguous_day_first_and_month_first_dates():
    assert status({"age": 20}, {"minimum_age": 18, "deadline": "31/12/2031"}) == "eligible"
    assert status({"age": 20}, {"minimum_age": 18, "deadline": "12/31/2031"}) == "eligible"
    assert status({"age": 20}, {"minimum_age": 18, "deadline": "05/05/2031"}) == "eligible"


def test_missing_deadline_is_never_open():
    r = check_eligibility({"age": 20}, {"minimum_age": 18, "status": "open"}, today=TODAY)
    assert r["eligibility_status"] == "potentially_eligible"
    assert any("deadline" in m for m in r["missing_information"])


# ----------------------------------------------------- never claim unwarranted eligibility
def test_scholarship_with_no_criteria_is_not_eligible():
    r = check_eligibility({"age": 20, "nationality": "Pakistani"}, {"deadline": FUTURE, "status": "open"}, today=TODAY)
    assert r["eligibility_status"] == "insufficient_information"
    assert any("no eligibility criteria" in m for m in r["missing_information"])


def test_open_deadline_alone_does_not_make_potentially_eligible():
    r = run({}, {"minimum_cgpa": 3.0})
    assert r["eligibility_status"] == "insufficient_information"


def test_empty_inputs_never_eligible():
    for p, s in [({}, {}), (None, None), ({"age": 20}, {}), ({}, {"nationality": "Pakistani"})]:
        assert check_eligibility(p, s, today=TODAY)["eligibility_status"] != "eligible"


def test_nan_and_blank_scholarship_values_are_unknown():
    nan = float("nan")
    r = run({"age": 20}, {"minimum_age": nan, "nationality": "  ", "minimum_cgpa": None})
    assert r["eligibility_status"] == "insufficient_information"


def test_return_shape_and_deduplicated_missing():
    r = run({}, {"minimum_age": 18, "maximum_age": 25})
    assert set(r) == {"eligibility_status", "reasons", "missing_information"}
    assert len(r["missing_information"]) == len(set(r["missing_information"]))


# ------------------------------------------- decimals must survive text cleaning
def test_decimal_points_are_preserved_in_numbers():
    assert status({"marks": "75.5%"}, {"minimum_marks": 75}) == "eligible"
    assert status({"marks": "74.5%"}, {"minimum_marks": 75}) == "ineligible"
    assert status({"cgpa": "3.75"}, {"minimum_cgpa": 3.7}) == "eligible"
    assert status({"cgpa": "3.65"}, {"minimum_cgpa": "3.7"}) == "ineligible"
    assert status({"age": "19.5"}, {"minimum_age": 19}) == "eligible"
