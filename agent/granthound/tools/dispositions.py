"""Pure, deterministic mapping from fetch/date/diff flags to a Disposition.

Moved out of scripts/run_local.py so it ships inside the deployable
`agent/` package (agentcore ships `agent/` only; a script under `scripts/`
never reaches the deployed agent). No AWS imports, no I/O, no clock reads.
"""

from datetime import date

from granthound.store.models import DateScan, Disposition


def has_future_dated_date(date_scan: DateScan, today: date) -> bool:
    """True if the scan found at least one year-present date >= today.

    Pure derivation over a DateScan -- used by suggest_disposition's
    yearless-date-vs-year-trap check ("is there a real future-dated date
    anywhere on the page to vouch for a yearless mention").
    """
    return any(
        d.year_present and d.iso is not None and date.fromisoformat(d.iso) >= today
        for d in date_scan.dates
    )


def suggest_disposition(
    *,
    http_status: int | None,
    transport_error: bool,
    all_dates_past: bool,
    has_yearless_date: bool,
    has_future_dated_date: bool,
    dates_contradict: bool,
    is_first_eval: bool,
    date_lines_changed: bool,
    prior_was_unreachable: bool = False,
) -> Disposition:
    """Pure, deterministic disposition mapping -- no I/O, no clock.

    Precedence (first match wins):
      1. PAGE_UNREACHABLE   -- transport failed, or HTTP status >= 400
      2. STALE_DATE_SUSPECT -- every dated (year-present) date is in the past
      3. YEAR_TRAP_SUSPECT  -- a yearless date appears with no future-dated
                               date anywhere on the page to vouch for it
      4. DATE_CONTRADICTION -- two future deadline-context dates disagree
                               by more than the contradiction gap
      5. ADDED              -- first eval for this program
      6. CHANGED_DEADLINE   -- a date-bearing line changed vs. the baseline
                               snapshot (the last one that had a snapshot)
      7. VERIFIED_LIVE      -- the immediately prior eval was PAGE_UNREACHABLE
                               and the page is back, unchanged (recovery)
      8. REVERIFIED_LIVE    -- subsequent eval, unchanged
    """
    if transport_error or (http_status is not None and http_status >= 400):
        return Disposition.PAGE_UNREACHABLE
    if all_dates_past:
        return Disposition.STALE_DATE_SUSPECT
    if has_yearless_date and not has_future_dated_date:
        return Disposition.YEAR_TRAP_SUSPECT
    if dates_contradict:
        return Disposition.DATE_CONTRADICTION
    if is_first_eval:
        return Disposition.ADDED
    if date_lines_changed:
        return Disposition.CHANGED_DEADLINE
    if prior_was_unreachable:
        return Disposition.VERIFIED_LIVE
    return Disposition.REVERIFIED_LIVE
