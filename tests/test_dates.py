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


def test_invalid_calendar_date_is_skipped_entirely():
    scan = extract_dates("Deadline 02/30/2026 for late applicants.", TODAY)
    assert scan.dates == []
    assert scan.has_yearless_date is False


def test_month_year_without_day_has_year_present():
    scan = extract_dates("Grant cycle opens May 2026 with rolling review.", TODAY)
    assert len(scan.dates) == 1
    assert scan.dates[0].year_present is True
    assert scan.dates[0].iso == "2026-05-01"
    assert scan.has_yearless_date is False


# --- Regression: month tokens lack word boundaries (final review finding 1) ---
# Reproduced against the pre-fix regex: each of these phantom-matched a
# month abbreviation/name embedded inside an unrelated word, setting
# has_yearless_date=True and risking a false YEAR_TRAP_SUSPECT.


def test_month_abbreviation_inside_street_address_not_matched():
    scan = extract_dates("Our office at 20 Marion Street", TODAY)
    assert scan.dates == []
    assert scan.has_yearless_date is False


def test_month_abbreviation_inside_place_name_not_matched():
    scan = extract_dates("Weimar 20", TODAY)
    assert scan.dates == []
    assert scan.has_yearless_date is False


def test_month_name_as_common_word_not_matched():
    scan = extract_dates("grantees may 20 percent", TODAY)
    assert scan.dates == []
    assert scan.has_yearless_date is False


# --- Regression: "Month YYYY" fabricates day=1, falsely flipping a
# current-month grant cycle to STALE_DATE_SUSPECT (final review finding 2) ---


def test_month_year_in_current_month_is_not_all_past():
    scan = extract_dates("Grant cycle opens August 2026. Apply now.", TODAY)
    assert scan.all_dates_past is False


def test_month_year_in_a_past_month_is_all_past():
    scan = extract_dates("Cycle was May 2026.", TODAY)
    assert scan.all_dates_past is True


# --- Regression: _is_deadline_context substring containment false-positives
# inside words, e.g. "close" inside "enclosed" (final review finding 6) ---


def test_close_substring_inside_word_is_not_a_deadline_false_positive():
    # "enclosed" contains the substring "close" but is not the word "close".
    # Under substring matching this wrongly tags the October 1 date as a
    # deadline-context date, and since a second, genuine deadline
    # ("Grant deadline: December 15, 2026") sits more than 30 days later,
    # the page is wrongly flagged as self-contradicting. Word-boundary
    # matching must leave the October 1 date out of deadline context, so
    # only one real deadline exists and there is no contradiction.
    text = (
        "The enclosed form accompanies this October 1, 2026 filing for our records. "
        "This community foundation supports youth mentorship, arts access, and neighborhood "
        "health initiatives throughout the metropolitan area every fiscal year with a broad "
        "range of programs designed to serve historically underinvested communities. "
        "Grant deadline: December 15, 2026."
    )
    scan = extract_dates(text, TODAY)
    assert scan.dates_contradict is False
