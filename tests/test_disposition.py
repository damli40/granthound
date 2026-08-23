"""TDD for granthound.tools.dispositions.suggest_disposition -- the pure, deterministic mapping
from fetch/date/diff flags to a Disposition, pinned in task-7-brief.md:

  http_status >= 400 or transport error  -> PAGE_UNREACHABLE
  all_dates_past                         -> STALE_DATE_SUSPECT
  has_yearless_date and not any
    year_present future date             -> YEAR_TRAP_SUSPECT
  dates_contradict                       -> DATE_CONTRADICTION
  else: first eval                       -> ADDED
        subsequent, date lines changed   -> CHANGED_DEADLINE
        subsequent, unchanged            -> REVERIFIED_LIVE

Checks are precedence-ordered (PAGE_UNREACHABLE beats every date flag, a
date flag beats the ADDED/REVERIFIED_LIVE/CHANGED_DEADLINE split), so each
test below sets only the one flag under test and leaves the rest at their
"clean page" default to prove that ordering rather than just the mapping.
"""

from granthound.store.models import Disposition
from granthound.tools.dispositions import suggest_disposition

CLEAN = dict(
    http_status=200,
    transport_error=False,
    all_dates_past=False,
    has_yearless_date=False,
    has_future_dated_date=True,
    dates_contradict=False,
    is_first_eval=False,
    date_lines_changed=False,
)


def _case(**overrides):
    kwargs = {**CLEAN, **overrides}
    return suggest_disposition(**kwargs)


def test_http_error_status_is_unreachable():
    assert _case(http_status=404, transport_error=False) == Disposition.PAGE_UNREACHABLE


def test_transport_error_is_unreachable_even_without_status():
    assert _case(http_status=None, transport_error=True) == Disposition.PAGE_UNREACHABLE


def test_unreachable_beats_every_other_flag():
    # A page that both 500s and would otherwise look contradictory must
    # still report PAGE_UNREACHABLE -- precedence, not just presence.
    assert (
        _case(http_status=500, dates_contradict=True, all_dates_past=True)
        == Disposition.PAGE_UNREACHABLE
    )


def test_all_dates_past_is_stale_suspect():
    assert _case(all_dates_past=True) == Disposition.STALE_DATE_SUSPECT


def test_yearless_with_no_future_dated_date_is_year_trap():
    assert (
        _case(has_yearless_date=True, has_future_dated_date=False)
        == Disposition.YEAR_TRAP_SUSPECT
    )


def test_yearless_with_a_future_dated_date_is_not_year_trap():
    # A yearless mention next to a real future-dated deadline is not a
    # trap -- the page also carries legitimate evidence it is current.
    assert (
        _case(has_yearless_date=True, has_future_dated_date=True)
        == Disposition.REVERIFIED_LIVE
    )


def test_dates_contradict_flags_contradiction():
    assert _case(dates_contradict=True) == Disposition.DATE_CONTRADICTION


def test_first_eval_with_clean_dates_is_added():
    assert _case(is_first_eval=True) == Disposition.ADDED


def test_subsequent_eval_unchanged_is_reverified_live():
    assert _case(is_first_eval=False, date_lines_changed=False) == Disposition.REVERIFIED_LIVE


def test_subsequent_eval_with_date_line_change_is_changed_deadline():
    assert _case(is_first_eval=False, date_lines_changed=True) == Disposition.CHANGED_DEADLINE


def test_recovery_from_unreachable_prior_is_verified_live():
    from granthound.store.models import Disposition
    from granthound.tools.dispositions import suggest_disposition

    result = suggest_disposition(
        http_status=200,
        transport_error=False,
        all_dates_past=False,
        has_yearless_date=False,
        has_future_dated_date=True,
        dates_contradict=False,
        is_first_eval=False,
        date_lines_changed=False,
        prior_was_unreachable=True,
    )
    assert result is Disposition.VERIFIED_LIVE


def test_recovery_with_a_moved_date_line_is_still_changed_deadline():
    from granthound.store.models import Disposition
    from granthound.tools.dispositions import suggest_disposition

    result = suggest_disposition(
        http_status=200,
        transport_error=False,
        all_dates_past=False,
        has_yearless_date=False,
        has_future_dated_date=True,
        dates_contradict=False,
        is_first_eval=False,
        date_lines_changed=True,
        prior_was_unreachable=True,
    )
    assert result is Disposition.CHANGED_DEADLINE
