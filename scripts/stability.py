"""Verdict stability between each program's two latest evals, from the live store.

Usage: .venv/bin/python scripts/stability.py
Prints one line per program and a flip count. Paste the summary into the
README's known-limits section; never quote a fit score without it.
"""

import os
import sys
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
from granthound.export import verdict_flips  # noqa: E402
from granthound.store.protocol import LiveStore  # noqa: E402


def main() -> int:
    Settings.from_env()
    rows = verdict_flips(LiveStore())
    compared = [r for r in rows if r["runs_compared"] == 2]
    for r in rows:
        mark = "FLIP" if r["flipped"] else "same" if r["runs_compared"] == 2 else "one-run"
        print(f"{r['program_id']:<32} {str(r['previous']):<12} -> {str(r['latest']):<12} {mark}  ({r['previous_disposition']} -> {r['latest_disposition']})")
    flips = sum(1 for r in compared if r["flipped"])
    print(f"\n{len(compared)} programs with two evals; {flips} verdict flip(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
