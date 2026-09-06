"""Write web/data.json from the store (or from the test fixtures with --sample).

Usage:
  .venv/bin/python scripts/export_inbox.py [--out web/data.json]
  .venv/bin/python scripts/export_inbox.py --sample [--out web/data.json]

--sample runs the scripted in-memory graph from tests/fakes.py and exports
that, so the page can be built and viewed with no AWS session. Never
deploy a --sample export.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "agent"))
sys.path.insert(0, str(REPO_ROOT))


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(REPO_ROOT / ".env")

from granthound.export import build_export  # noqa: E402
from granthound.seeds.profile import DEFAULT_SEED_PATH, load_seed_file  # noqa: E402


def sample_store():
    from datetime import datetime as dt

    from granthound.pipeline.run import run_batch
    from tests.fakes import ORG, PAGES, good_analyst, good_clerk, good_scout, good_verifier, make_fetcher, scripted_executors, seeded_store

    store = seeded_store()
    store.put_program_meta({"program_id": "fixtures/sunset-fund", "url": "https://example.invalid/fixtures/sunset-fund/index.html", "funder": "Sunset Community Fund", "source_type": "fixture", "is_fixture": True})
    ex = scripted_executors(good_scout, good_verifier, good_analyst, good_clerk)
    run_batch(["p-live", "p-dead", "p-down"], dt(2026, 8, 21, 12, 0, tzinfo=timezone.utc), store=store, fetcher=make_fetcher(PAGES), org=ORG, executors=ex)
    return store, ORG


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the inbox data file.")
    parser.add_argument("--out", default=str(REPO_ROOT / "web" / "data.json"))
    parser.add_argument("--sample", action="store_true", help="Export the scripted test run instead of the live store.")
    args = parser.parse_args()

    if args.sample:
        store, org = sample_store()
    else:
        from granthound.config import Settings
        from granthound.store.protocol import LiveStore

        Settings.from_env()
        store = LiveStore()
        org = load_seed_file(DEFAULT_SEED_PATH).org

    data = build_export(store, org, now=datetime.now(timezone.utc), sample=args.sample)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    from granthound.calendar import build_ics
    ics_path = out.with_name("deadlines.ics")
    ics_path.write_text(build_ics(data["programs"], now=datetime.now(timezone.utc)), encoding="utf-8", newline="")

    s = data["stats"]
    unreadable = s["receipts_unreadable"]
    tag = "SAMPLE" if args.sample else "live"
    print(
        f"wrote {out} [{tag}] programs={s['programs']} runs={s['runs']} "
        f"verdicts={s['verdict_counts']} receipts_unreadable={unreadable} ics={ics_path}"
    )
    # The file is written either way -- the page still needs it. The non-zero
    # exit is how a scheduled export says "evidence I have a receipt for is
    # missing from the bucket" instead of finishing quietly.
    return 1 if unreadable else 0


if __name__ == "__main__":
    sys.exit(main())
