"""Regression tests: deduplication must never merge distinct programs/cycles."""

import pytest

import src.data_import as di
from src.data_import import import_workbook
from src.database import init_db
from tests.helpers import all_rows, count_rows, write_sheet, write_workbook


def _wb(tmp_path, rows, name="w.xlsx"):
    return write_sheet(tmp_path / name, rows)


def test_complete_key_reimport_is_not_duplicated(tmp_path):
    rows = [{"Scholarship Name": "Award", "Provider": "Org", "Deadline": "2031-01-31"}]
    wb = _wb(tmp_path, rows)
    r1 = import_workbook(wb)
    r2 = import_workbook(wb)
    assert r1["records_inserted"] == 1
    assert r2["records_inserted"] == 0 and r2["records_duplicate"] == 1
    assert count_rows() == 1


def test_different_deadlines_are_different_cycles(tmp_path):
    wb = _wb(tmp_path, [
        {"Scholarship Name": "Award", "Provider": "Org", "Deadline": "2031-01-31"},
        {"Scholarship Name": "Award", "Provider": "Org", "Deadline": "2032-01-31"},
    ])
    assert import_workbook(wb)["records_inserted"] == 2
    assert count_rows() == 2


def test_same_date_in_different_formats_is_one_cycle(tmp_path):
    wb = _wb(tmp_path, [
        {"Scholarship Name": "Award", "Provider": "Org", "Deadline": "2031-12-31"},
        {"Scholarship Name": "Award", "Provider": "  ORG ", "Deadline": "31/12/2031"},
    ])
    r = import_workbook(wb)
    assert r["records_inserted"] == 1 and r["records_duplicate"] == 1


def test_missing_provider_does_not_merge_different_programs(tmp_path):
    """Same name, no provider on either side, different deadlines -> two programs."""
    wb = _wb(tmp_path, [
        {"Scholarship Name": "Merit Award", "Provider": None, "Deadline": "2031-01-31"},
        {"Scholarship Name": "Merit Award", "Provider": None, "Deadline": "2032-01-31"},
    ])
    r = import_workbook(wb)
    assert r["records_inserted"] == 2 and r["records_duplicate"] == 0
    assert any("lack provider" in w for w in r["warnings"])


def test_missing_deadline_does_not_merge_different_programs(tmp_path):
    wb = _wb(tmp_path, [
        {"Scholarship Name": "Merit Award", "Provider": "Org", "Deadline": None, "Description": "Undergraduate track"},
        {"Scholarship Name": "Merit Award", "Provider": "Org", "Deadline": None, "Description": "Masters track"},
    ])
    r = import_workbook(wb)
    assert r["records_inserted"] == 2 and r["records_duplicate"] == 0


def test_provider_present_vs_missing_are_distinct(tmp_path):
    wb = _wb(tmp_path, [
        {"Scholarship Name": "Award", "Provider": "Org A", "Deadline": "2031-01-31"},
        {"Scholarship Name": "Award", "Provider": None, "Deadline": "2031-01-31"},
    ])
    assert import_workbook(wb)["records_inserted"] == 2


def test_incomplete_key_records_survive_exact_reimport_once(tmp_path):
    """Records missing deadline/provider are inserted once, and re-importing the same file adds nothing."""
    wb = _wb(tmp_path, [
        {"Scholarship Name": "Open Call", "Provider": None, "Deadline": None, "Description": "x"},
        {"Scholarship Name": "Open Call", "Provider": None, "Deadline": None, "Description": "y"},
    ])
    r1 = import_workbook(wb)
    r2 = import_workbook(wb)
    assert r1["records_inserted"] == 2
    assert r2["records_inserted"] == 0 and r2["records_duplicate"] == 2
    assert count_rows() == 2


def test_unparseable_deadline_counts_as_missing_key(tmp_path):
    wb = _wb(tmp_path, [
        {"Scholarship Name": "Award", "Provider": "Org", "Deadline": "TBA"},
        {"Scholarship Name": "Award", "Provider": "Org", "Deadline": "Rolling"},
    ])
    r = import_workbook(wb)
    assert r["records_inserted"] == 2
    assert any("malformed deadline" in w for w in r["warnings"])


def test_external_id_same_id_is_duplicate_even_if_deadline_missing(tmp_path):
    grid = [["opportunity_id", "opportunity_name", "sponsor"],
            ["X-1", "Award One", "Org"]]
    wb = write_workbook(tmp_path / "w.xlsx", {"Master": grid})
    assert import_workbook(wb)["records_inserted"] == 1
    r = import_workbook(wb)
    assert r["records_inserted"] == 0 and r["records_duplicate"] == 1


def test_external_id_different_ids_never_merge(tmp_path):
    grid = [["opportunity_id", "opportunity_name", "sponsor", "deadline_date"],
            ["X-1", "Award", "Org", "2031-01-31"],
            ["X-2", "Award", "Org", "2031-01-31"]]
    wb = write_workbook(tmp_path / "w.xlsx", {"Master": grid})
    assert import_workbook(wb)["records_inserted"] == 2


def test_supplementary_sheets_with_same_ids_do_not_duplicate(tmp_path):
    master = [["opportunity_id", "opportunity_name", "sponsor"], ["X-1", "Award One", "Org"]]
    view = [["opportunity_id", "opportunity_name", "study_level"], ["X-1", "Award One", "Master"]]
    wb = write_workbook(tmp_path / "w.xlsx", {"Master": master, "Masters": view})
    r = import_workbook(wb)
    assert r["records_inserted"] == 1 and r["records_duplicate"] == 1


def test_duplicate_rows_inside_one_sheet_collapse(tmp_path):
    wb = _wb(tmp_path, [
        {"Scholarship Name": "Award", "Provider": "Org", "Deadline": "2031-01-31"},
        {"Scholarship Name": "Award", "Provider": "Org", "Deadline": "2031-01-31"},
    ])
    r = import_workbook(wb)
    assert r["records_inserted"] == 1 and r["records_duplicate"] == 1


def test_duplicate_check_failure_reports_error_and_does_not_insert(tmp_path, monkeypatch):
    def boom(cursor, record):
        raise RuntimeError("simulated lookup failure")
    monkeypatch.setattr(di, "_find_duplicate", boom)
    wb = _wb(tmp_path, [{"Scholarship Name": "Award", "Provider": "Org", "Deadline": "2031-01-31"}])
    r = import_workbook(wb)
    assert r["records_inserted"] == 0
    assert any("Duplicate check failed" in e and "NOT inserted" in e for e in r["errors"])
    assert count_rows() == 0


def test_sheet_failure_rolls_back_whole_sheet(tmp_path, monkeypatch):
    """An unexpected error half-way through a sheet leaves NOTHING from that sheet behind,
    and the summary does not claim rows that were rolled back."""
    calls = {"n": 0}
    real = di._row_to_raw_json

    def flaky(values):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("simulated mid-sheet failure")
        return real(values)

    monkeypatch.setattr(di, "_row_to_raw_json", flaky)
    wb = _wb(tmp_path, [
        {"Scholarship Name": f"Award {i}", "Provider": "Org", "Deadline": "2031-01-31"} for i in range(4)
    ])
    r = import_workbook(wb)
    assert r["records_inserted"] == 0
    assert r["sheets_processed"] == 0
    assert any("rolled back" in e and "simulated mid-sheet failure" in e for e in r["errors"])
    assert count_rows() == 0


def test_failed_sheet_does_not_undo_earlier_sheets(tmp_path, monkeypatch):
    real = di._row_to_raw_json
    state = {"sheet2": False}

    def flaky(values):
        if "Bad Sheet Award" in values.values():
            raise RuntimeError("boom")
        return real(values)

    monkeypatch.setattr(di, "_row_to_raw_json", flaky)
    hdr = ["Scholarship Name", "Provider", "Deadline"]
    wb = write_workbook(tmp_path / "w.xlsx", {
        "Good": [hdr, ["Good Award", "Org", "2031-01-31"]],
        "Bad": [hdr, ["Bad Sheet Award", "Org", "2031-01-31"]],
    })
    r = import_workbook(wb)
    assert r["records_inserted"] == 1 and r["sheets_processed"] == 1
    assert [row["name"] for row in all_rows()] == ["Good Award"]
    assert any("Sheet 'Bad' rolled back" in e for e in r["errors"])


def test_failed_insert_is_reported_not_counted(tmp_path, monkeypatch):
    """A row whose INSERT fails is an error and is not counted as inserted."""
    wb = _wb(tmp_path, [
        {"Scholarship Name": "Good", "Provider": "Org", "Deadline": "2031-01-31"},
        {"Scholarship Name": "Bad", "Provider": "Org", "Deadline": "2031-02-01"},
    ])
    init_db()
    from src.database import get_connection
    conn = get_connection()
    conn.execute("CREATE TRIGGER block_bad BEFORE INSERT ON scholarships "
                 "WHEN NEW.name = 'Bad' BEGIN SELECT RAISE(ABORT, 'blocked'); END;")
    conn.commit()
    conn.close()
    r = import_workbook(wb)
    assert r["records_inserted"] == 1
    assert any("Bad" not in e and "row" in e and "blocked" in e for e in r["errors"])
    assert [row["name"] for row in all_rows()] == ["Good"]
