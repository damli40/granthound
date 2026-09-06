from datetime import datetime, timezone

from granthound.calendar import build_ics

NOW = datetime(2026, 9, 6, 8, 0, tzinfo=timezone.utc)


def program(**over):
    base = {
        "program_id": "p-live", "funder": "Riverbend, Fund; Inc", "url": "https://x.org/live",
        "verdict": "APPLY", "is_fixture": False,
        "decision_package": {"deadlines": [
            {"iso": "2026-10-05", "kind": "full_application", "days_until": 29, "is_past": False, "collides_with": [], "day_fabricated": False},
            {"iso": "2026-09-10", "kind": "loi", "days_until": 4, "is_past": False, "collides_with": ["fall launch"], "day_fabricated": False},
            {"iso": "2026-08-01", "kind": "other", "days_until": -36, "is_past": True, "collides_with": [], "day_fabricated": False},
        ]},
    }
    base.update(over)
    return base


def test_one_all_day_event_per_future_deadline_with_escaping_and_crlf():
    ics = build_ics([program()], now=NOW)
    assert ics.startswith("BEGIN:VCALENDAR\r\n") and ics.endswith("END:VCALENDAR\r\n")
    assert ics.count("BEGIN:VEVENT") == 2                      # the past one is skipped
    assert "DTSTART;VALUE=DATE:20261005" in ics and "DTSTART;VALUE=DATE:20260910" in ics
    assert "SUMMARY:Riverbend\\, Fund\\; Inc: LOI" in ics        # comma and semicolon escaped, kind label fixed
    assert "UID:granthound-p-live-2026-09-10-loi@granthound" in ics
    assert "DESCRIPTION:Verdict APPLY. Collides with: fall launch. https://x.org/live" in ics
    assert "\n" not in ics.replace("\r\n", "")                  # every line break is CRLF


def test_month_only_deadline_lands_on_month_end_and_says_so():
    p = program(decision_package={"deadlines": [
        {"iso": "2026-09-01", "kind": "full_application", "days_until": 24, "is_past": False, "collides_with": [], "day_fabricated": True},
    ]})
    ics = build_ics([p], now=NOW)
    assert "DTSTART;VALUE=DATE:20260930" in ics
    assert "SUMMARY:Riverbend\\, Fund\\; Inc: Full application (month only)" in ics


def test_programs_without_a_package_or_with_no_future_dates_produce_no_events():
    ics = build_ics([program(decision_package=None), program(program_id="p2", decision_package={"deadlines": []})], now=NOW)
    assert ics.count("BEGIN:VEVENT") == 0 and "BEGIN:VCALENDAR" in ics


def test_fixture_events_are_labelled():
    ics = build_ics([program(is_fixture=True)], now=NOW)
    assert "SUMMARY:[TEST FUNDER] Riverbend\\, Fund\\; Inc: LOI" in ics
