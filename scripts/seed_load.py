"""Load the org's seed list into program META items.

Usage:
  .venv/bin/python scripts/seed_load.py [--file agent/granthound/seeds/maya.yml] [--dry-run]

META first, always: run_local/run_batch update META pointers with an
attribute_exists guard, so a program that was never seeded is skipped (and
flagged) rather than ghost-created. Re-running is safe: pointer fields the
pipeline wrote are preserved (build_meta_item).
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "agent"))


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

from granthound.config import Settings  # noqa: E402
from granthound.seeds.profile import DEFAULT_SEED_PATH, build_meta_item, load_seed_file  # noqa: E402
from granthound.store.protocol import LiveStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed program META items from a seed file.")
    parser.add_argument("--file", default=str(DEFAULT_SEED_PATH))
    parser.add_argument("--dry-run", action="store_true", help="Print the items; write nothing.")
    args = parser.parse_args()

    Settings.from_env()
    seed_file = load_seed_file(Path(args.file))
    store = LiveStore()
    seeded_at = datetime.now(timezone.utc).isoformat()

    written = 0
    for seed in sorted(seed_file.seeds, key=lambda s: s.id):
        existing = None if args.dry_run else store.get_program(seed.id)
        item = build_meta_item(seed, seed_file.org.name, existing, seeded_at)
        action = "would write" if args.dry_run else ("update" if existing else "create")
        print(f"{action} META {seed.id}: {seed.funder} <{seed.url}>")
        if not args.dry_run:
            store.put_program_meta(item)
            written += 1
    print(f"{written} META item(s) written from {args.file} ({len(seed_file.seeds)} seeds)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
