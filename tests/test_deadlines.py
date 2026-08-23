from datetime import date, datetime

from granthound.seeds.profile import CommitmentWindow
from granthound.store.models import DeadlineKind, DeadlinePick
from granthound.tools.deadlines import deadline_math

TODAY = date(2026, 8, 21)
WINDOWS = [CommitmentWindow(label="fall program launch", start="2026-09-01", end="2026-09-20")]


def test_days_until_and_flags():
    picks = [DeadlinePick(iso="2026-09-01", kind=DeadlineKind.FULL_APPLICATION)]
    [m] = deadline_math(picks, TODAY, WINDOWS)
    assert m.days_until == 11 and m.within_14_days is True and m.is_past is False
    assert m.collides_with == ["fall program launch"]


def test_past_deadline_is_flagged_not_dropped():
    picks = [DeadlinePick(iso="2026-08-01", kind=DeadlineKind.LOI)]
    [m] = deadline_math(picks, TODAY, WINDOWS)
    assert m.is_past is True and m.days_until == -20 and m.within_14_days is False


def test_no_collision_outside_every_window():
    picks = [DeadlinePick(iso="2026-10-15", kind=DeadlineKind.FULL_APPLICATION)]
    [m] = deadline_math(picks, TODAY, WINDOWS)
    assert m.collides_with == [] and m.within_14_days is False


def test_output_is_sorted_and_deduplicated_regardless_of_input_order():
    picks = [
        DeadlinePick(iso="2026-10-15", kind=DeadlineKind.FULL_APPLICATION),
        DeadlinePick(iso="2026-09-01", kind=DeadlineKind.LOI),
        DeadlinePick(iso="2026-10-15", kind=DeadlineKind.FULL_APPLICATION),
    ]
    out = deadline_math(picks, TODAY, WINDOWS)
    assert [(m.iso, m.kind) for m in out] == [("2026-09-01", DeadlineKind.LOI), ("2026-10-15", DeadlineKind.FULL_APPLICATION)]
    assert out == deadline_math(list(reversed(picks)), TODAY, WINDOWS)


def test_window_edges_are_inclusive():
    picks = [DeadlinePick(iso="2026-09-20", kind=DeadlineKind.OTHER), DeadlinePick(iso="2026-09-21", kind=DeadlineKind.OTHER)]
    first, second = deadline_math(picks, TODAY, WINDOWS)
    assert first.collides_with == ["fall program launch"] and second.collides_with == []


def test_a_window_built_from_a_yaml_datetime_is_usable_here():
    """The two halves of the defect this file and profile.py share: whatever
    CommitmentWindow stores must be parseable by date.fromisoformat below. A
    YAML `start: 2026-09-01 00:00:00` arrives as a datetime, and storing its
    full isoformat used to raise here, once per program, mid-run."""
    windows = [CommitmentWindow(label="fall program launch", start=datetime(2026, 9, 1, 0, 0), end=date(2026, 9, 20))]
    [m] = deadline_math([DeadlinePick(iso="2026-09-01", kind=DeadlineKind.LOI)], TODAY, windows)
    assert m.collides_with == ["fall program launch"]


def test_a_month_only_date_counts_to_the_end_of_the_month_it_named():
    """A page that printed only "September 2026" never named a day.

    The scanner stores 2026-09-01 and marks the day fabricated, and the
    liveness rule already treats such a date as current through the last
    day of that month. The same rule has to hold in the arithmetic, or a
    package tells a human that a still-open deadline passed a fortnight
    ago. `iso` stays exactly what the scanner stored -- only the counting
    moves to the end of the month.
    """
    today = date(2026, 9, 15)
    picks = [DeadlinePick(iso="2026-09-01", kind=DeadlineKind.FULL_APPLICATION, day_fabricated=True)]
    [m] = deadline_math(picks, today, WINDOWS)
    assert m.iso == "2026-09-01" and m.day_fabricated is True
    assert m.is_past is False and m.days_until == 15 and m.within_14_days is False


def test_a_printed_full_date_is_untouched_by_the_fabricated_day_rule():
    """The control for the test above: same ISO, same today, day NOT
    fabricated, so the arithmetic is the plain day-1 count it always was."""
    today = date(2026, 9, 15)
    picks = [DeadlinePick(iso="2026-09-01", kind=DeadlineKind.FULL_APPLICATION)]
    [m] = deadline_math(picks, today, WINDOWS)
    assert m.day_fabricated is False
    assert m.is_past is True and m.days_until == -14 and m.within_14_days is False


def test_a_month_only_date_in_a_past_month_is_still_past():
    """End-of-month counting extends a date, it does not resurrect one."""
    today = date(2026, 9, 15)
    picks = [DeadlinePick(iso="2026-08-01", kind=DeadlineKind.LOI, day_fabricated=True)]
    [m] = deadline_math(picks, today, WINDOWS)
    assert m.is_past is True and m.days_until == -15
