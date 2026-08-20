import difflib

from granthound.store.models import DiffResult
from granthound.tools.dates import DATE_CANDIDATE_RE


def diff_snapshots(old_norm: str, new_norm: str) -> DiffResult:
    """Generate diff between snapshots, detecting date-line changes.

    Positional slicing (body = lines[2:]) skips unified_diff metadata headers
    (--- and +++ lines always emitted first when hunks exist; identical case
    returns early). This avoids content-prefix matching issues where genuine
    lines starting with -- (markdown rules ---, frontmatter) would be filtered
    out by startswith checks. With n=1 context, we always have exactly 2 header
    lines before body when any hunk exists, making slice-based extraction safe.
    """
    if old_norm == new_norm:
        return DiffResult(
            changed=False, date_lines_changed=False, added_lines=0, removed_lines=0, diff_text=""
        )
    lines = list(
        difflib.unified_diff(
            old_norm.splitlines(), new_norm.splitlines(), lineterm="", n=1
        )
    )
    body = lines[2:]
    added = [l for l in body if l.startswith("+")]
    removed = [l for l in body if l.startswith("-")]
    date_lines_changed = any(DATE_CANDIDATE_RE.search(l) for l in added + removed)
    return DiffResult(
        changed=True,
        date_lines_changed=date_lines_changed,
        added_lines=len(added),
        removed_lines=len(removed),
        diff_text="\n".join(lines),
    )
