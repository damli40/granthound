import difflib

from granthound.store.models import DiffResult
from granthound.tools.dates import DATE_CANDIDATE_RE


def diff_snapshots(old_norm: str, new_norm: str) -> DiffResult:
    if old_norm == new_norm:
        return DiffResult(
            changed=False, date_lines_changed=False, added_lines=0, removed_lines=0, diff_text=""
        )
    lines = list(
        difflib.unified_diff(
            old_norm.splitlines(), new_norm.splitlines(), lineterm="", n=1
        )
    )
    added = [l for l in lines if l.startswith("+") and not l.startswith("+++")]
    removed = [l for l in lines if l.startswith("-") and not l.startswith("---")]
    date_lines_changed = any(DATE_CANDIDATE_RE.search(l) for l in added + removed)
    return DiffResult(
        changed=True,
        date_lines_changed=date_lines_changed,
        added_lines=len(added),
        removed_lines=len(removed),
        diff_text="\n".join(lines),
    )
