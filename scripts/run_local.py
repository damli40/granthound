"""GrantHound local runner -- one cycle, with or without the models.

Two paths, one script:

  --no-llm   the deterministic slice on its own: fetch a funder page,
             normalize + digest it, write the raw/normalized snapshot to S3,
             scan for dates, map the deterministic flags to a Disposition,
             write an EVAL row, print one line. Exactly one program.

  (default)  the full graph: Scout -> Verifier -> Analyst -> Clerk over one
             or more programs, then finalization (one EVAL per program, one
             RUN row with per-node token usage and the model id each node
             actually billed). This is the path that costs money.

Usage:
  .venv/bin/python scripts/run_local.py --no-llm --program-id <id> [--url <override>]
  .venv/bin/python scripts/run_local.py --program-id <id> [--program-id <id> ...] [--url <override>]
  .venv/bin/python scripts/run_local.py --all [--seeds <path>] [--limit <n>]

--url overrides the page checked for this run (an ad-hoc check of a URL that
is not in the store yet). It applies to exactly one program, so it is a usage
error alongside --all or a second --program-id. Without it the program's
stored META url is used -- scripts/seed_load.py writes those.

No hidden clocks: main() reads the wall clock exactly once, as a single
UTC-aware `at` datetime, and hands it to the pipeline, which derives
everything time-related from that one value (the EVAL sort keys, the run id,
the snapshot `fetched_at` strings, and `today` for the date scan). Two
programs in one batch are therefore judged against the same day.
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

from granthound.config import Settings  # noqa: E402
from granthound.pipeline.deterministic import (  # noqa: E402
    evaluate_program,
    persist_deterministic,
)
from granthound.pipeline.run import run_batch  # noqa: E402
from granthound.seeds.profile import DEFAULT_SEED_PATH, load_seed_file  # noqa: E402
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
    parser = argparse.ArgumentParser(description="GrantHound local runner.")
    parser.add_argument("--program-id", action="append", default=[], help="Program id; repeat for several.")
    parser.add_argument("--all", action="store_true", help="Every program in the seed file.")
    parser.add_argument("--no-llm", action="store_true", help="Deterministic path only (one program).")
    parser.add_argument("--url", default=None, help="URL override (one program only).")
    parser.add_argument("--seeds", default=None, help="Seed file path (default: the packaged maya.yml).")
    parser.add_argument("--limit", type=int, default=None, help="Cap how many programs run.")
    args = parser.parse_args()

    # Settings.from_env() first: it is the one place that names every missing
    # environment variable at once, and it must run before any model is built.
    settings = Settings.from_env()
    seed_file = load_seed_file(Path(args.seeds) if args.seeds else DEFAULT_SEED_PATH)
    store = LiveStore()
    at = datetime.now(timezone.utc)

    program_ids = list(args.program_id)
    if args.all:
        program_ids = [seed.id for seed in seed_file.seeds]
    if args.limit is not None:
        program_ids = program_ids[: args.limit]
    if not program_ids:
        print("error: pass --program-id (repeatable) or --all", file=sys.stderr)
        return 2
    if args.url is not None and len(program_ids) != 1:
        print("error: --url applies to exactly one --program-id", file=sys.stderr)
        return 2

    if args.no_llm:
        if len(program_ids) != 1:
            print("error: --no-llm runs exactly one program", file=sys.stderr)
            return 2
        program_id = program_ids[0]
        url = args.url or (store.get_program(program_id) or {}).get("url")
        if not url:
            print(f"error: no --url given and no stored URL for '{program_id}'", file=sys.stderr)
            return 2
        try:
            result = run_one(program_id, url, at)
        except Exception as exc:  # noqa: BLE001 -- top-level CLI entrypoint
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
        sha = result["sha256"][:8] if result["sha256"] else "n/a"
        print(
            f"{result['program_id']} disposition={result['disposition'].value} "
            f"dates={result['date_count']} yearless={result['yearless_count']} "
            f"all_past={result['all_dates_past']} sha={sha} -> {result['eval_sk']}"
        )
        return 0

    summary = run_batch(
        program_ids, at,
        store=store, fetcher=fetch_page, org=seed_file.org, settings=settings,
        url_overrides={program_ids[0]: args.url} if args.url else None,
    )
    for outcome in summary.outcomes:
        # outcome.flags, not the EVAL row: meta_missing and meta_pointer_failed
        # are raised after the row is assembled, so the durable row never
        # carries them and only this object can report them.
        flags = f" flags={','.join(outcome.flags)}" if outcome.flags else ""
        # eval_sk is None when the EVAL write itself failed (the program still
        # has a verdict; there is just no row to point at).
        target = outcome.eval_sk or "NO EVAL ROW"
        print(f"{outcome.program_id} {outcome.verdict.value} {outcome.disposition.value}{flags} -> {target}")
    usage = summary.run_item["node_usage"]
    total = sum(node["total_tokens"] for node in usage.values())
    per_node = " ".join(f"{node}={usage[node]['total_tokens']}" for node in sorted(usage))
    print(f"run {summary.run_id} status={summary.status} tokens: total={total} {per_node}")
    print(f"models: {summary.run_item['node_models']}")
    if summary.errors:
        for line in summary.errors:
            print(f"error: {line}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
