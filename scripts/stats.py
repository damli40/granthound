"""Print the measured table for README / Devpost / posts from web/data.json.

Usage: .venv/bin/python scripts/stats.py [web/data.json]
Every published number is pasted from this output with its run id. Nothing
is typed by hand.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "agent"))

from granthound.export import render_stats  # noqa: E402


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "web" / "data.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    # The real path, not a hardcoded one: the footer is a provenance claim, and
    # a table generated from a sample file must not say it came from the live one.
    print(render_stats(data, source=str(path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
