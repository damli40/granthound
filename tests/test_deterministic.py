from datetime import datetime, timedelta, timezone

from granthound.pipeline.deterministic import evaluate_program, persist_deterministic
from granthound.store.models import DeterministicEval, Disposition
from tests.fakes import UNREACHABLE, MemoryStore, html_page, make_fetcher

AT = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
URL = "https://example.org/grants"
LIVE = html_page("Applications are due October 15, 2026. Awards up to $25,000.")
LIVE_MOVED = html_page("Applications are due October 22, 2026. Awards up to $25,000.")
# The generic tweak has to land on its OWN line, not appended to the
# deadline sentence. diff_snapshots works per line: any changed line that
# contains a date candidate counts as a date-line change, so a tweak glued
# onto the end of the "due October 15, 2026" line would legitimately read
# as a date-line change and this test would be asserting the opposite of
# what the code does. A trailing paragraph is what a real nav/social tweak
# looks like in normalized markdown anyway.
LIVE_NAV_TWEAK = LIVE.replace("</main>", "<p>Follow us on social.</p></main>")


def test_first_run_is_added_with_receipt_and_no_eval_write():
    store = MemoryStore()
    det = evaluate_program("p1", URL, AT, store=store, fetcher=make_fetcher({URL: (200, LIVE)}))
    assert isinstance(det, DeterministicEval)
    assert det.disposition is Disposition.ADDED
    assert det.is_first_eval is True
    assert det.snapshot_receipt is not None and det.snapshot_receipt.http_status == 200
    assert det.snapshot_receipt.s3_norm in store.objects
    assert det.date_scan is not None and det.date_scan.all_dates_past is False
    assert det.diff_receipt is None
    assert det.norm_text and "October 15, 2026" in det.norm_text
    assert store.evals == {}


def test_norm_text_never_appears_in_a_dump():
    store = MemoryStore()
    det = evaluate_program("p1", URL, AT, store=store, fetcher=make_fetcher({URL: (200, LIVE)}))
    assert "norm_text" not in det.model_dump()


def test_persist_deterministic_writes_one_eval_row():
    store = MemoryStore()
    det = evaluate_program("p1", URL, AT, store=store, fetcher=make_fetcher({URL: (200, LIVE)}))
    sk = persist_deterministic(det, store=store, at=AT)
    assert sk.startswith("EVAL#2026-08-21T12:00:00+00:00#run-20260821T120000Z")
    row = store.get_last_eval("p1")
    assert row["disposition"] == "added"
    assert row["snapshot_receipt"]["sha256"] == det.snapshot_receipt.sha256
    assert "norm_text" not in row


def test_transport_failure_is_unreachable_without_snapshot():
    store = MemoryStore()
    det = evaluate_program("p1", URL, AT, store=store, fetcher=make_fetcher({URL: UNREACHABLE}))
    assert det.disposition is Disposition.PAGE_UNREACHABLE
    assert det.transport_error is True and det.http_status is None
    assert det.snapshot_receipt is None and det.date_scan is None and det.diff_receipt is None
    assert store.objects == {}


def test_http_404_is_unreachable_with_status():
    store = MemoryStore()
    det = evaluate_program("p1", URL, AT, store=store, fetcher=make_fetcher({URL: (404, "<html>gone</html>")}))
    assert det.disposition is Disposition.PAGE_UNREACHABLE
    assert det.http_status == 404 and det.transport_error is False


def _run_twice(store, first_page, second_page):
    det1 = evaluate_program("p1", URL, AT, store=store, fetcher=make_fetcher({URL: (200, first_page)}))
    persist_deterministic(det1, store=store, at=AT)
    at2 = AT + timedelta(hours=1)
    det2 = evaluate_program("p1", URL, at2, store=store, fetcher=make_fetcher({URL: (200, second_page)}))
    return det1, det2


def test_unchanged_page_is_reverified_with_a_no_change_receipt():
    store = MemoryStore()
    det1, det2 = _run_twice(store, LIVE, LIVE)
    assert det2.disposition is Disposition.REVERIFIED_LIVE
    assert det2.is_first_eval is False
    assert det2.diff_receipt is not None
    assert det2.diff_receipt.changed is False and det2.diff_receipt.s3_key is None
    assert det2.diff_receipt.old_sha256 == det1.snapshot_receipt.sha256


def test_date_line_change_is_changed_deadline_with_a_stored_diff():
    store = MemoryStore()
    _, det2 = _run_twice(store, LIVE, LIVE_MOVED)
    assert det2.disposition is Disposition.CHANGED_DEADLINE
    assert det2.diff_receipt.date_lines_changed is True
    assert det2.diff_receipt.s3_key in store.objects
    assert "October 22, 2026" in store.objects[det2.diff_receipt.s3_key]


def test_generic_only_change_stays_reverified_but_records_the_diff():
    store = MemoryStore()
    _, det2 = _run_twice(store, LIVE, LIVE_NAV_TWEAK)
    assert det2.disposition is Disposition.REVERIFIED_LIVE
    assert det2.diff_receipt.changed is True
    assert det2.diff_receipt.date_lines_changed is False
    assert det2.diff_receipt.s3_key in store.objects


def test_recovery_after_outage_diffs_against_last_good_snapshot_and_reads_verified_live():
    store = MemoryStore()
    det1 = evaluate_program("p1", URL, AT, store=store, fetcher=make_fetcher({URL: (200, LIVE)}))
    persist_deterministic(det1, store=store, at=AT)
    at2 = AT + timedelta(hours=12)
    det2 = evaluate_program("p1", URL, at2, store=store, fetcher=make_fetcher({URL: UNREACHABLE}))
    persist_deterministic(det2, store=store, at=at2)
    at3 = AT + timedelta(hours=24)
    det3 = evaluate_program("p1", URL, at3, store=store, fetcher=make_fetcher({URL: (200, LIVE)}))
    assert det3.prior_was_unreachable is True
    assert det3.disposition is Disposition.VERIFIED_LIVE
    assert det3.diff_receipt.old_sha256 == det1.snapshot_receipt.sha256
    det3b = evaluate_program("p1", URL, at3, store=store, fetcher=make_fetcher({URL: (200, LIVE_MOVED)}))
    assert det3b.disposition is Disposition.CHANGED_DEADLINE


def test_first_ever_fetch_failing_then_recovering_reads_added_not_verified_live():
    store = MemoryStore()
    det1 = evaluate_program("p1", URL, AT, store=store, fetcher=make_fetcher({URL: UNREACHABLE}))
    assert det1.disposition is Disposition.PAGE_UNREACHABLE
    persist_deterministic(det1, store=store, at=AT)

    at2 = AT + timedelta(hours=12)
    det2 = evaluate_program("p1", URL, at2, store=store, fetcher=make_fetcher({URL: (200, LIVE)}))
    # A prior EVAL row exists, so this is not the first eval, and the prior
    # one was unreachable -- the two conditions that used to yield
    # VERIFIED_LIVE. But no snapshot was ever stored, so nothing was
    # compared and "back, unchanged" has no evidence behind it. This run is
    # the first look at the page's content, which is what ADDED means.
    assert det2.is_first_eval is False
    assert det2.prior_was_unreachable is True
    assert det2.diff_receipt is None
    assert det2.disposition is Disposition.ADDED


def test_non_utc_at_stamps_run_id_and_snapshot_key_in_utc():
    store = MemoryStore()
    at_local = datetime(2026, 8, 21, 13, 0, tzinfo=timezone(timedelta(hours=1)))  # 12:00 UTC
    det = evaluate_program("p1", URL, at_local, store=store, fetcher=make_fetcher({URL: (200, LIVE)}))

    # The Z in the stamp format is a literal, so these only tell the truth
    # if `at` is converted first -- 13:00+01:00 is 12:00 Zulu, not 13:00.
    assert det.run_id == "run-20260821T120000Z"
    assert det.fetched_at == "20260821T120000Z"
    assert det.snapshot_receipt.fetched_at == "20260821T120000Z"
    assert "20260821T120000Z" in det.snapshot_receipt.s3_norm

    # The payoff: put_evaluation normalizes the SK to UTC on its own, so an
    # unconverted run id would sit an hour ahead of the SK that carries it.
    sk = persist_deterministic(det, store=store, at=at_local)
    assert sk == "EVAL#2026-08-21T12:00:00+00:00#run-20260821T120000Z"
