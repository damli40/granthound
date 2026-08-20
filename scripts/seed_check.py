"""Seed-candidate shape checker: rejects JS-only shells before they reach the
real pipeline.

A page that renders its content client-side (React/Vue/etc.) returns an
almost-empty HTML shell to a plain GET -- fetch_page never runs a browser,
so that shell is all extract_dates would ever see. Two signals catch this:
normalized text under 5000 chars, or zero DATE_CANDIDATE_RE hits (a real
grant page mentions at least one date somewhere, even "rolling" pages
usually name a fiscal year or an "as of" date). Either signal alone means
reject.

Usage:
  .venv/bin/python scripts/seed_check.py <urls-file>

<urls-file>: one URL per line; blank lines and lines starting with '#' are
skipped.

Prints `KEEP <url> (<detail>)` or `REJECT <url> (<reason>)` per line.
Exits 0 always -- this is a report for a human to read before the seed-
assembly session, not a pass/fail gate.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENT_DIR = REPO_ROOT / "agent"
sys.path.insert(0, str(AGENT_DIR))

import requests  # noqa: E402

from granthound.tools.dates import DATE_CANDIDATE_RE  # noqa: E402
from granthound.tools.fetch import fetch_page, normalize_html  # noqa: E402

MIN_TEXT_CHARS = 5000


def check_url(url: str) -> tuple[bool, str]:
    """Return (keep, reason_or_detail) for one candidate URL."""
    try:
        status, body = fetch_page(url)
    except requests.RequestException as exc:
        return False, f"transport error: {exc}"
    if status >= 400:
        return False, f"http status {status}"

    norm = normalize_html(body)
    text_len = len(norm)
    date_hits = len(DATE_CANDIDATE_RE.findall(norm))

    reasons = []
    if text_len < MIN_TEXT_CHARS:
        reasons.append(f"{text_len} chars < {MIN_TEXT_CHARS} (js-shell suspect)")
    if date_hits == 0:
        reasons.append("zero date-candidate hits")
    if reasons:
        return False, ", ".join(reasons)
    return True, f"{text_len} chars, {date_hits} date hits"


def read_urls(path: Path) -> list[str]:
    urls = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        urls.append(line)
    return urls


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: seed_check.py <urls-file>", file=sys.stderr)
        return 0

    urls_file = Path(sys.argv[1])
    if not urls_file.exists():
        print(f"error: no such file: {urls_file}", file=sys.stderr)
        return 0

    for url in read_urls(urls_file):
        keep, detail = check_url(url)
        label = "KEEP" if keep else "REJECT"
        print(f"{label} {url} ({detail})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
