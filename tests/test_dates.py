from datetime import date

from granthound.tools.dates import extract_dates

TODAY = date(2026, 8, 20)


def test_full_date_extracted_iso():
    scan = extract_dates("Applications are due October 15, 2026 at noon.", TODAY)
    assert scan.dates[0].iso == "2026-10-15"
    assert scan.dates[0].year_present is True
    assert scan.has_yearless_date is False


def test_year_trap_yearless_date_flagged():
    scan = extract_dates("Applications due March 15. Apply early!", TODAY)
    assert scan.has_yearless_date is True
    assert scan.dates[0].year_present is False
    assert scan.dates[0].iso is None


def test_all_dates_past_flags_stale_page():
    scan = extract_dates(
        "Winners announced June 22, 2025. The deadline was May 1, 2025.", TODAY
    )
    assert scan.all_dates_past is True


def test_mixed_dates_not_all_past():
    scan = extract_dates("Opened May 1, 2026. Deadline November 30, 2026.", TODAY)
    assert scan.all_dates_past is False


def test_contradicting_future_deadlines():
    scan = extract_dates(
        "Submission deadline: October 1, 2026. Apply by December 15, 2026.", TODAY
    )
    assert scan.dates_contradict is True


def test_close_deadlines_do_not_contradict():
    scan = extract_dates(
        "Deadline October 1, 2026 (11:59pm). Applications due October 3, 2026.", TODAY
    )
    assert scan.dates_contradict is False


def test_no_dates_no_flags():
    scan = extract_dates("We fund youth programs across the county.", TODAY)
    assert scan.dates == []
    assert scan.all_dates_past is False
    assert scan.has_yearless_date is False
