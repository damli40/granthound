"""The deterministic layer: fetch -> snapshot -> dates -> diff -> disposition.

Moved here from scripts/run_local.py (M1 Task 7) so the same code runs under
the Scout's fetch_and_snapshot tool, the --no-llm CLI path, and the tests.
Rules carried over unchanged:
  - evidence (raw + normalized snapshot, diff) is written at fetch time;
  - the EVAL row is NOT written here -- callers persist (persist_deterministic
    for the no-LLM path, pipeline.finalize for the graph);
  - `at` is the single run clock; today/fetched_at/run_id derive from it;
  - the diff baseline is the last eval WITH a snapshot (walks back past
    outages), while is_first_eval/prior_was_unreachable use the plain last
    eval.
"""

from collections.abc import Callable
from datetime import date, datetime

import requests

from granthound.store.models import (
    DeterministicEval,
    DiffReceipt,
    Disposition,
    SnapshotReceipt,
)
from granthound.store.protocol import Store
from granthound.tools.dates import extract_dates
from granthound.tools.diff import diff_snapshots
from granthound.tools.dispositions import has_future_dated_date, suggest_disposition
from granthound.tools.fetch import digest, normalize_html

Fetcher = Callable[[str], tuple[int, str]]


def run_id_for(at: datetime) -> str:
    return f"run-{at.strftime('%Y%m%dT%H%M%SZ')}"


def evaluate_program(
    program_id: str, url: str, at: datetime, *, store: Store, fetcher: Fetcher
) -> DeterministicEval:
    today: date = at.date()
    fetched_at = at.strftime("%Y%m%dT%H%M%SZ")
    run_id = run_id_for(at)

    last_eval = store.get_last_eval(program_id)
    is_first_eval = last_eval is None
    prior_was_unreachable = (
        last_eval is not None and last_eval.get("disposition") == Disposition.PAGE_UNREACHABLE.value
    )

    transport_error = False
    http_status: int | None = None
    body = ""
    try:
        http_status, body = fetcher(url)
    except requests.RequestException:
        transport_error = True

    if transport_error or (http_status is not None and http_status >= 400):
        disposition = suggest_disposition(
            http_status=http_status,
            transport_error=transport_error,
            all_dates_past=False,
            has_yearless_date=False,
            has_future_dated_date=False,
            dates_contradict=False,
            is_first_eval=is_first_eval,
            date_lines_changed=False,
            prior_was_unreachable=prior_was_unreachable,
        )
        return DeterministicEval(
            program_id=program_id,
            url=url,
            run_id=run_id,
            fetched_at=fetched_at,
            disposition=disposition,
            http_status=http_status,
            transport_error=transport_error,
            snapshot_receipt=None,
            date_scan=None,
            diff_receipt=None,
            is_first_eval=is_first_eval,
            prior_was_unreachable=prior_was_unreachable,
            has_future_dated_date=False,
            norm_text=None,
        )

    norm = normalize_html(body)
    sha256 = digest(norm)
    raw_key, norm_key = store.put_snapshot(program_id, fetched_at, sha256, body, norm)

    date_scan = extract_dates(norm, today)
    future_dated = has_future_dated_date(date_scan, today)

    diff_receipt: DiffReceipt | None = None
    baseline = store.get_last_eval(program_id, with_snapshot=True)
    if baseline is not None:
        prev_receipt = baseline.get("snapshot_receipt") or {}
        if prev_receipt.get("s3_norm"):
            prev_norm = store.get_norm_snapshot(prev_receipt["s3_norm"])
            result = diff_snapshots(prev_norm, norm)
            old_sha = prev_receipt.get("sha256", "")
            s3_key = (
                store.put_diff(program_id, fetched_at, old_sha, sha256, result.diff_text)
                if result.changed
                else None
            )
            diff_receipt = DiffReceipt(
                s3_key=s3_key,
                old_sha256=old_sha,
                changed=result.changed,
                date_lines_changed=result.date_lines_changed,
                added_lines=result.added_lines,
                removed_lines=result.removed_lines,
            )

    disposition = suggest_disposition(
        http_status=http_status,
        transport_error=False,
        all_dates_past=date_scan.all_dates_past,
        has_yearless_date=date_scan.has_yearless_date,
        has_future_dated_date=future_dated,
        dates_contradict=date_scan.dates_contradict,
        is_first_eval=is_first_eval,
        date_lines_changed=bool(diff_receipt and diff_receipt.date_lines_changed),
        prior_was_unreachable=prior_was_unreachable,
    )

    return DeterministicEval(
        program_id=program_id,
        url=url,
        run_id=run_id,
        fetched_at=fetched_at,
        disposition=disposition,
        http_status=http_status,
        transport_error=False,
        snapshot_receipt=SnapshotReceipt(
            sha256=sha256,
            s3_raw=raw_key,
            s3_norm=norm_key,
            fetched_at=fetched_at,
            http_status=http_status,
        ),
        date_scan=date_scan,
        diff_receipt=diff_receipt,
        is_first_eval=is_first_eval,
        prior_was_unreachable=prior_was_unreachable,
        has_future_dated_date=future_dated,
        norm_text=norm,
    )


def persist_deterministic(det: DeterministicEval, *, store: Store, at: datetime) -> str:
    """Write the no-LLM EVAL row (the M1 shape plus diff_receipt/run bookkeeping)."""
    item = {**det.model_dump(mode="json"), "stage": "deterministic"}
    return store.put_evaluation(det.program_id, det.run_id, item, at=at)
