"""Print the measured table for README / Devpost / posts from web/data.json.

Usage: .venv/bin/python scripts/stats.py [web/data.json] [--since YYYY-MM-DD]
Every published number is pasted from this output with its run id. Nothing
is typed by hand.

--since keeps only the runs whose `at` timestamp is on or after that UTC
date before recomputing the run-count and per-model token rows, and prints
which slice it kept as the table's first row. It never touches `programs`
(verdict/disposition/quote counts still cover everything in the store) or
the export file itself -- only what this one printout shows. Use it once
older runs were made against a model that is no longer what's running (a
model swap during development, say): those runs stay in the store for
history, but a token total that mixes them in never reaches zero for the
model that stopped being used.
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "agent"))

from granthound.export import build_stats, filter_runs_since, render_stats  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=str(REPO_ROOT / "web" / "data.json"))
    parser.add_argument(
        "--since",
        default=None,
        metavar="YYYY-MM-DD",
        help="Keep only runs at/after this UTC date; recomputes the run-count and token rows on that subset.",
    )
    args = parser.parse_args()

    path = Path(args.path)
    data = json.loads(path.read_text(encoding="utf-8"))

    if args.since:
        all_runs = data["runs"]
        try:
            kept = filter_runs_since(all_runs, args.since)
        except ValueError as exc:
            print(f"--since {args.since!r}: {exc}", file=sys.stderr)
            return 2
        # The real path, not a hardcoded one: the footer is a provenance claim, and
        # a table generated from a sample file must not say it came from the live one.
        data = {**data, "stats": build_stats(data["programs"], kept)}
        lines = render_stats(data, source=str(path)).split("\n")
        # lines[0] is the header row, lines[1] the "|---|---|" separator --
        # this goes first among the data rows, so every number below it is
        # read with its scope already stated, not after the fact.
        lines.insert(2, f"| Runs from: {args.since} ({len(kept)} of {len(all_runs)} runs in the store) |  |")
        print("\n".join(lines))
    else:
        print(render_stats(data, source=str(path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
