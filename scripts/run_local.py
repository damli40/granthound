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
UTC-aware `at` datetime, and passes it to granthound.pipeline.deterministic,
which derives everything time-related (the EVAL SK, `run_id`, the snapshot
`fetched_at` string, and `today` for date-scan comparisons) from that one
value.
"""

import argparse
import os
import sys
from datetime import datetime, timezone
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

from granthound.pipeline.deterministic import (  # noqa: E402
    evaluate_program,
    persist_deterministic,
)
from granthound.store import ddb  # noqa: E402 -- main() resolves a stored META url
from granthound.store.protocol import LiveStore  # noqa: E402
from granthound.tools.fetch import fetch_page  # noqa: E402


def run_one(program_id: str, url: str, at: datetime) -> dict:
    """One deterministic fetch-through-EVAL cycle (the --no-llm path).

    Business logic lives in granthound.pipeline.deterministic; this wrapper
    only binds the live store and the real fetcher and flattens the result
    for the console line in main().
    """
    store = LiveStore()
    det = evaluate_program(program_id, url, at, store=store, fetcher=fetch_page)
    eval_sk = persist_deterministic(det, store=store, at=at)
    dates = det.date_scan.dates if det.date_scan else []
    return {
        "program_id": program_id,
        "disposition": det.disposition,
        "date_count": len(dates),
        "yearless_count": sum(1 for d in dates if not d.year_present),
        "all_dates_past": det.date_scan.all_dates_past if det.date_scan else False,
        "sha256": det.snapshot_receipt.sha256 if det.snapshot_receipt else None,
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
