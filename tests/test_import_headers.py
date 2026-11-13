"""Regression tests: ambiguous Excel headers must never be mapped silently."""

import pytest

from src.database import init_db
from src.data_import import AMBIGUOUS_HEADERS, COLUMN_MAP, import_workbook, _normalize_col
from tests.helpers import all_rows, raw, write_sheet, write_workbook

# canonical columns an ambiguous header could be wrongly written into
CANONICAL_COLUMNS = [
    "nationality", "study_destination", "eligible_provinces", "eligible_cities", "eligible_domiciles",
    "minimum_marks", "minimum_cgpa", "household_income_limit", "application_url", "source_url",
    "status", "location",
]

AMBIGUOUS_SAMPLES = {
    "Country": "Pakistan",
    "State": "Punjab",
    "Marks": "85",
    "CGPA": "3.5",
    "Income": "50000",
    "URL": "https://example.com/a",
    "Link": "https://example.com/b",
    "City": "Lahore",
    "Province": "Sindh",
}


@pytest.mark.parametrize("header", sorted(AMBIGUOUS_SAMPLES))
def test_ambiguous_header_is_unmapped_preserved_and_warned(tmp_path, header):
    wb = write_sheet(tmp_path / "w.xlsx", [{
        "Scholarship Name": "Test Award", "Provider": "Test Org", "Deadline": "2031-01-31",
        header: AMBIGUOUS_SAMPLES[header],
    }])
    result = import_workbook(wb)

    assert result["records_inserted"] == 1, result
    row = all_rows()[0]
    # no canonical column received the ambiguous value
    for col in CANONICAL_COLUMNS:
        assert row[col] is None, f"{header!r} leaked into {col}"
    # original value preserved
    assert str(raw(row)[header]) == AMBIGUOUS_SAMPLES[header]
    # clear warning naming the header
    assert any(f"'{header}'" in w and "unmapped" in w for w in result["warnings"]), result["warnings"]


def test_ambiguous_headers_not_in_column_map():
    for norm in AMBIGUOUS_HEADERS:
        assert norm not in COLUMN_MAP, norm
    for header in AMBIGUOUS_SAMPLES:
        assert _normalize_col(header) not in COLUMN_MAP


def test_explicit_headers_still_map(tmp_path):
    wb = write_sheet(tmp_path / "w.xlsx", [{
        "Scholarship Name": "Explicit Award", "Provider": "Org", "Deadline": "2031-01-31",
        "Study Destination": "UK", "Minimum CGPA": 3.2, "Minimum Marks": 70,
        "Application URL": "https://example.com/apply", "Source URL": "https://example.com/src",
    }])
    result = import_workbook(wb)
    assert result["records_inserted"] == 1
    row = all_rows()[0]
    assert row["study_destination"] == "UK"
    assert row["minimum_cgpa"] == pytest.approx(3.2)
    assert row["minimum_marks"] == pytest.approx(70)
    assert row["application_url"] == "https://example.com/apply"
    assert row["source_url"] == "https://example.com/src"
    assert not any("Ambiguous" in w for w in result["warnings"])


def test_ambiguous_header_does_not_shadow_explicit_header(tmp_path):
    """'Country' next to an explicit 'Nationality' must not overwrite or duplicate it."""
    wb = write_sheet(tmp_path / "w.xlsx", [{
        "Scholarship Name": "A", "Provider": "P", "Deadline": "2031-01-31",
        "Nationality": "Pakistani", "Country": "Germany",
    }])
    import_workbook(wb)
    row = all_rows()[0]
    assert row["nationality"] == "Pakistani"
    assert row["study_destination"] is None
    assert raw(row)["Country"] == "Germany"


def test_column_overrides_resolve_ambiguity_explicitly(tmp_path):
    wb = write_sheet(tmp_path / "w.xlsx", [{
        "Scholarship Name": "A", "Provider": "P", "Deadline": "2031-01-31", "Country": "Germany",
    }])
    result = import_workbook(wb, column_overrides={"Country": "study_destination"})
    assert result["records_inserted"] == 1
    row = all_rows()[0]
    assert row["study_destination"] == "Germany"
    assert row["nationality"] is None
    assert not any("'Country'" in w and "unmapped" in w for w in result["warnings"])


def test_invalid_column_override_reports_error_and_imports_nothing(tmp_path):
    init_db()
    wb = write_sheet(tmp_path / "w.xlsx", [{"Scholarship Name": "A", "Country": "Germany"}])
    result = import_workbook(wb, column_overrides={"Country": "not_a_field"})
    assert result["errors"] and result["records_inserted"] == 0
    assert all_rows() == []


def test_header_row_detected_below_title_rows(tmp_path):
    wb = write_sheet(tmp_path / "w.xlsx", [{
        "Scholarship Name": "Titled Sheet Award", "Provider": "Org", "Deadline": "2031-01-31",
    }], title_rows=4)
    result = import_workbook(wb)
    assert result["records_inserted"] == 1, result
    assert all_rows()[0]["name"] == "Titled Sheet Award"
    assert any("header row detected at row 5" in w for w in result["warnings"])


def test_header_on_first_row_is_unchanged(tmp_path):
    wb = write_sheet(tmp_path / "w.xlsx", [{"Scholarship Name": "Plain", "Provider": "Org"}])
    result = import_workbook(wb)
    assert result["records_inserted"] == 1
    assert not any("header row detected" in w for w in result["warnings"])


def test_sixty_field_style_headers(tmp_path):
    """Synthetic workbook that mimics the real master sheet's header names."""
    grid = [
        ["Canonical opportunities"], [], ["2 unique records"], [],
        ["opportunity_id", "opportunity_name", "sponsor", "study_level", "destination_country",
         "minimum_grade", "income_threshold", "nationality_rule", "deadline_date",
         "application_status", "official_source_url", "last_verified_date"],
        ["T-0001", "Synthetic Award One", "Sponsor A", "Undergraduate", "Pakistan",
         "60%", "PKR 100,000 per month", "Pakistani nationals", "2031-03-01", "open",
         "https://example.com/one", "2026-10-17"],
        ["T-0002", "Synthetic Award Two", "Sponsor B", "Master", "UK",
         "3.0", None, None, None, "not_announced", "https://example.com/two", "2026-10-17"],
    ]
    wb = write_workbook(tmp_path / "w.xlsx", {"MASTER_60_FIELDS": grid})
    result = import_workbook(wb)
    assert result["records_inserted"] == 2, result
    rows = all_rows()
    assert rows[0]["external_id"] == "T-0001"
    assert rows[0]["name"] == "Synthetic Award One"
    assert rows[0]["provider"] == "Sponsor A"
    assert rows[0]["education_level"] == "Undergraduate"
    assert rows[0]["study_destination"] == "Pakistan"
    assert rows[0]["deadline"] == "2031-03-01"
    assert rows[0]["status"] == "open"
    # grade/income are ambiguous (percentage vs CGPA; period/currency) -> never imported as criteria
    assert rows[0]["minimum_marks"] is None and rows[0]["minimum_cgpa"] is None
    assert rows[0]["household_income_limit"] is None
    assert raw(rows[0])["minimum_grade"] == "60%"
    assert any("minimum_grade" in w and "unmapped" in w for w in result["warnings"])


@pytest.mark.parametrize("sheet", ["FIELD_DICTIONARY", "EXCLUSIONS_DEDUP", "VERIFY_QUEUE", "START_HERE"])
def test_metadata_sheets_are_skipped(tmp_path, sheet):
    wb = write_workbook(tmp_path / "w.xlsx", {sheet: [["name", "provider"], ["Should Not Import", "X"]]})
    result = import_workbook(wb)
    assert result["records_inserted"] == 0
    assert any("Skipped" in w and sheet in w for w in result["warnings"])
