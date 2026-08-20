"""GrantHound vertical-slice runner -- deterministic path, no LLM.

Fetches a funder page, normalizes + digests it, writes the raw/normalized
snapshot to S3, extracts date candidates, maps the deterministic flags to a
Disposition (no LLM in this slice -- the M2 Verifier refines this, it never
contradicts it), writes an EVAL item to DynamoDB, and prints a one-line
verdict summary.

Usage:
  .venv/bin/python scripts/run_local.py --program-id <id> --no-llm [--url <override>]

--no-llm is required in this plan: the flag exists so M2 can add the LLM
verification path later without renaming the flag, but this slice has no
LLM path to fall back to, so omitting it is a usage error, not a silent
default.

--url overrides the page checked for this run (also used for ad-hoc,
one-off checks of a URL that isn't in the store at all yet). Without
--url, the program's stored META url is used; this slice does not write a
META item itself (out of scope -- see Interfaces block in the task brief),
so --url is effectively required until a later task's seed_load populates
META.

No hidden clocks: main() reads the wall clock exactly once, as a single
UTC-aware `at` datetime, and run_one derives everything time-related
(the EVAL SK via store.ddb.put_evaluation's `at`, the snapshot `fetched_at`
string, and `today` for date-scan comparisons) from that one value.
"""

import argparse
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_DIR = REPO_ROOT / "agent"
sys.path.insert(0, str(AGENT_DIR))


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader -- only sets vars not already in the environment.

    Mirrors scripts/store_smoke.py's loader (python-dotenv is not
    installed in this project). Called at import time, before the
    granthound.store imports below, because ddb.py/s3.py read AWS_REGION
    at their own module-import time (GRANTHOUND_TABLE/GRANTHOUND_BUCKET
    are read lazily inside each call, but AWS_REGION is not) -- importing
    them first would silently fall back to AWS_REGION's default instead
    of whatever .env says.
    """
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(REPO_ROOT / ".env")

import requests  # noqa: E402

from granthound.store import ddb, s3  # noqa: E402
from granthound.store.models import Disposition, SnapshotReceipt  # noqa: E402
from granthound.tools.dates import extract_dates  # noqa: E402
from granthound.tools.diff import diff_snapshots  # noqa: E402
from granthound.tools.fetch import digest, fetch_page, normalize_html  # noqa: E402


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
) -> Disposition:
    """Pure, deterministic disposition mapping -- no I/O, no clock.

    Precedence (first match wins), per task-7-brief.md:
      1. PAGE_UNREACHABLE   -- transport failed, or HTTP status >= 400
      2. STALE_DATE_SUSPECT -- every dated (year-present) date is in the past
      3. YEAR_TRAP_SUSPECT  -- a yearless date appears with no future-dated
                               date anywhere on the page to vouch for it
      4. DATE_CONTRADICTION -- two future deadline-context dates disagree
                               by more than the contradiction gap
      5. else: ADDED (first eval for this program) / CHANGED_DEADLINE
               (subsequent eval, a date line changed vs. the prior
               snapshot) / REVERIFIED_LIVE (subsequent eval, unchanged)
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
    return Disposition.REVERIFIED_LIVE


def run_one(program_id: str, url: str, at: datetime) -> dict:
    """Run one fetch-through-EVAL cycle for a program. Pure business logic --
    argparse and console printing live in main().

    `at` is the single run-start timestamp (UTC-aware, read once by the
    caller) that this function derives every time-related value from:
    `today` for date-scan comparisons, `fetched_at` for the snapshot key
    and SnapshotReceipt, and it is passed straight through to
    ddb.put_evaluation's required `at` keyword for the EVAL item's SK.
    """
    today: date = at.date()
    fetched_at = at.strftime("%Y%m%dT%H%M%SZ")
    run_id = f"run-{fetched_at}"

    last_eval = ddb.get_last_eval(program_id)
    is_first_eval = last_eval is None

    transport_error = False
    http_status: int | None = None
    body = ""
    try:
        http_status, body = fetch_page(url)
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
        )
        eval_item = {
            "disposition": disposition.value,
            "url": url,
            "http_status": http_status,
            "transport_error": transport_error,
            "snapshot_receipt": None,
        }
        eval_sk = ddb.put_evaluation(program_id, run_id, eval_item, at=at)
        return {
            "program_id": program_id,
            "disposition": disposition,
            "date_count": 0,
            "yearless_count": 0,
            "all_dates_past": False,
            "sha256": None,
            "eval_sk": eval_sk,
        }

    norm = normalize_html(body)
    sha256 = digest(norm)
    raw_key, norm_key = s3.put_snapshot(program_id, fetched_at, sha256, body, norm)

    date_scan = extract_dates(norm, today)
    has_future_dated_date = any(
        d.year_present and d.iso is not None and date.fromisoformat(d.iso) >= today
        for d in date_scan.dates
    )

    date_lines_changed = False
    if last_eval is not None:
        prev_receipt = last_eval.get("snapshot_receipt")
        if prev_receipt and prev_receipt.get("s3_norm"):
            prev_norm = s3.get_norm_snapshot(prev_receipt["s3_norm"])
            diff_result = diff_snapshots(prev_norm, norm)
            date_lines_changed = diff_result.date_lines_changed
            if diff_result.changed:
                s3.put_diff(
                    program_id,
                    fetched_at,
                    prev_receipt.get("sha256", ""),
                    sha256,
                    diff_result.diff_text,
                )

    disposition = suggest_disposition(
        http_status=http_status,
        transport_error=False,
        all_dates_past=date_scan.all_dates_past,
        has_yearless_date=date_scan.has_yearless_date,
        has_future_dated_date=has_future_dated_date,
        dates_contradict=date_scan.dates_contradict,
        is_first_eval=is_first_eval,
        date_lines_changed=date_lines_changed,
    )

    snapshot_receipt = SnapshotReceipt(
        sha256=sha256,
        s3_raw=raw_key,
        s3_norm=norm_key,
        fetched_at=fetched_at,
        http_status=http_status,
    )
    eval_item = {
        "disposition": disposition.value,
        "url": url,
        "snapshot_receipt": snapshot_receipt.model_dump(),
        "date_scan": date_scan.model_dump(),
    }
    eval_sk = ddb.put_evaluation(program_id, run_id, eval_item, at=at)

    return {
        "program_id": program_id,
        "disposition": disposition,
        "date_count": len(date_scan.dates),
        "yearless_count": sum(1 for d in date_scan.dates if not d.year_present),
        "all_dates_past": date_scan.all_dates_past,
        "sha256": sha256,
        "eval_sk": eval_sk,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="GrantHound vertical-slice runner (deterministic, no LLM)."
    )
    parser.add_argument("--program-id", required=True, help="Program id, e.g. provisional-1")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        required=True,
        help="Required in this plan -- no LLM verification path exists yet.",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Override URL for this run (ad-hoc check, or first run before a "
        "stored program META exists).",
    )
    args = parser.parse_args()

    if args.url is not None:
        url = args.url
    else:
        program = ddb.get_program(args.program_id)
        if program is None or not program.get("url"):
            print(
                f"error: no --url given and no stored URL for program "
                f"'{args.program_id}'",
                file=sys.stderr,
            )
            return 2
        url = program["url"]

    at = datetime.now(timezone.utc)

    try:
        result = run_one(args.program_id, url, at)
    except Exception as exc:  # noqa: BLE001 -- top-level CLI entrypoint
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    sha_display = result["sha256"][:8] if result["sha256"] else "n/a"
    print(
        f"{result['program_id']} disposition={result['disposition'].value} "
        f"dates={result['date_count']} yearless={result['yearless_count']} "
        f"all_past={result['all_dates_past']} sha={sha_display} -> {result['eval_sk']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
