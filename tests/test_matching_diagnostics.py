"""Regression tests: matching diagnostics, error placeholders, sorting and DB failures."""

from datetime import date

import pytest

import src.matching as matching
from src.database import get_connection, init_db
from src.matching import find_matches
from tests.helpers import insert_row

TODAY = date(2026, 10, 18)
PROFILE = {"age": 20, "nationality": "Pakistani"}


def seed(**fields):
    init_db()
    base = {"deadline": "2031-06-15", "status": "open", "minimum_age": 18}
    base.update(fields)
    insert_row(**base)


# ------------------------------------------------------------------ item shape
def test_real_scholarships_are_labelled_and_have_diagnostics_list():
    seed(name="Real One", nationality="Pakistani")
    [item] = find_matches(PROFILE, today=TODAY)
    assert item["record_type"] == "scholarship"
    assert item["name"] == "Real One"
    assert item["diagnostics"] == []
    assert item["eligibility_status"] == "eligible"


class _BadRow:
    """A row object that cannot be converted to a dict."""
    def __iter__(self):
        raise TypeError("unreadable row")

    def keys(self):
        raise TypeError("unreadable row")

    def __getitem__(self, key):
        raise TypeError("unreadable row")


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, *a, **k):
        return _FakeCursor(self._rows)

    def close(self):
        pass


def test_unreadable_row_becomes_clearly_marked_error_item(monkeypatch):
    seed(name="Real One")
    init_db()
    conn = get_connection()
    real_rows = conn.execute("SELECT * FROM scholarships").fetchall()
    conn.close()
    monkeypatch.setattr(matching, "get_connection", lambda: _FakeConn(list(real_rows) + [_BadRow()]))

    results = find_matches(PROFILE, today=TODAY)
    kinds = [r["record_type"] for r in results]
    assert kinds == ["scholarship", "error"]
    err = results[-1]
    assert err["eligibility_status"] == "error"
    assert err["name"] is None and err["provider"] is None
    assert "unreadable row" in err["error"]
    assert err["diagnostics"] and "Could not read scholarship record" in err["diagnostics"][0]
    # an error item is never mistaken for a ranked status
    assert err["eligibility_status"] not in ("eligible", "potentially_eligible", "insufficient_information")


def test_error_items_follow_real_results_and_do_not_use_up_the_limit(monkeypatch):
    for i in range(3):
        seed(name=f"S{i}")
    conn = get_connection()
    rows = conn.execute("SELECT * FROM scholarships").fetchall()
    conn.close()
    monkeypatch.setattr(matching, "get_connection", lambda: _FakeConn([_BadRow()] + list(rows)))
    results = find_matches(PROFILE, limit=2, today=TODAY)
    assert [r["record_type"] for r in results] == ["scholarship", "scholarship", "error"]


def test_eligibility_exception_keeps_real_record_with_diagnostic(monkeypatch):
    seed(name="Breaks")
    seed(name="Fine")
    real = matching.check_eligibility

    def flaky(profile, scholarship, today=None):
        if scholarship["name"] == "Breaks":
            raise ValueError("bad data")
        return real(profile, scholarship, today=today)

    monkeypatch.setattr(matching, "check_eligibility", flaky)
    results = {r["name"]: r for r in find_matches(PROFILE, today=TODAY)}
    assert results["Breaks"]["record_type"] == "scholarship"
    assert results["Breaks"]["eligibility_status"] == "insufficient_information"
    assert any("ValueError" in d and "bad data" in d for d in results["Breaks"]["diagnostics"])
    assert results["Fine"]["diagnostics"] == []


# ------------------------------------------------------------------- sorting
def test_sort_by_status_then_parsed_deadline_with_unparseable_last():
    seed(name="late", deadline="2032-01-01")
    seed(name="early-iso", deadline="2031-01-05")
    seed(name="mid-dmy", deadline="15/12/2031")       # string sort would misplace this
    seed(name="tba", deadline="TBA")
    seed(name="none", deadline=None)
    names = [r["name"] for r in find_matches(PROFILE, today=TODAY)]
    assert names[:3] == ["early-iso", "mid-dmy", "late"]
    assert set(names[3:]) == {"tba", "none"}


def test_status_rank_beats_deadline():
    seed(name="eligible-late", deadline="2033-01-01", nationality="Pakistani")
    seed(name="unknown-early", deadline="2031-01-01", nationality=None, minimum_cgpa=3.0)
    names = [r["name"] for r in find_matches(PROFILE, today=TODAY)]
    assert names == ["eligible-late", "unknown-early"]


def test_malformed_deadlines_never_crash_sorting():
    for i, d in enumerate(["", "????", "2031-13-45", "01/02/2031", 2031, "31/12/2031"]):
        seed(name=f"d{i}", deadline=d)
    results = find_matches(PROFILE, today=TODAY)
    assert len(results) == 6
    assert results[0]["deadline"] == "31/12/2031"  # only parseable, unambiguous one comes first


def test_expired_and_ineligible_are_excluded_and_today_is_injectable():
    seed(name="expired", deadline="2026-10-01")
    seed(name="open")
    assert [r["name"] for r in find_matches(PROFILE, today=TODAY)] == ["open"]


def test_limit_clamping():
    for i in range(5):
        seed(name=f"s{i}")
    assert len(find_matches(PROFILE, limit=2, today=TODAY)) == 2
    assert len(find_matches(PROFILE, limit=0, today=TODAY)) == 5
    assert len(find_matches(PROFILE, limit="abc", today=TODAY)) == 5
    assert len(find_matches(PROFILE, limit=True, today=TODAY)) == 5
    assert len(find_matches(PROFILE, limit=10 ** 9, today=TODAY)) == 5


# -------------------------------------------------------- failures not silenced
def test_init_failure_is_raised_not_swallowed(monkeypatch):
    def boom():
        raise RuntimeError("disk unavailable")
    monkeypatch.setattr(matching, "init_db", boom)
    with pytest.raises(RuntimeError, match="disk unavailable"):
        find_matches(PROFILE)


def test_query_failure_is_raised_not_empty_list(monkeypatch):
    class Broken:
        def execute(self, *a, **k):
            raise RuntimeError("database disk image is malformed")

        def close(self):
            pass

    init_db()
    monkeypatch.setattr(matching, "get_connection", lambda: Broken())
    with pytest.raises(RuntimeError, match="malformed"):
        find_matches(PROFILE)


def test_connection_failure_is_raised(monkeypatch):
    init_db()

    def boom():
        raise RuntimeError("cannot open database")
    monkeypatch.setattr(matching, "get_connection", boom)
    with pytest.raises(RuntimeError, match="cannot open database"):
        find_matches(PROFILE)


def test_empty_database_returns_empty_list_only_when_truly_empty():
    init_db()
    assert find_matches(PROFILE, today=TODAY) == []
