"""Deadline arithmetic over dates the Clerk picked from the scanner's list.

Pure: no clock, no I/O. Results are sorted by (iso, kind) and deduplicated
so a human-facing list never depends on the order the model emitted picks.
A past deadline is flagged, not dropped -- a dead date on a live page is
exactly the kind of contradiction a human should see.
"""

from datetime import date

from granthound.seeds.profile import CommitmentWindow
from granthound.store.models import DeadlineMath, DeadlinePick

WITHIN_DAYS = 14


def deadline_math(
    picks: list[DeadlinePick], today: date, windows: list[CommitmentWindow]
) -> list[DeadlineMath]:
    unique = {(p.iso, p.kind): p for p in picks}
    out: list[DeadlineMath] = []
    for (iso, kind), _ in sorted(unique.items(), key=lambda kv: (kv[0][0], kv[0][1].value)):
        deadline = date.fromisoformat(iso)
        days = (deadline - today).days
        collides = sorted(
            w.label
            for w in windows
            if date.fromisoformat(w.start) <= deadline <= date.fromisoformat(w.end)
        )
        out.append(
            DeadlineMath(
                iso=iso,
                kind=kind,
                days_until=days,
                within_14_days=0 <= days <= WITHIN_DAYS,
                is_past=days < 0,
                collides_with=collides,
            )
        )
    return out
