"""Deadline arithmetic over dates the Clerk picked from the scanner's list.

Pure: no clock, no I/O. Results are sorted by (iso, kind) and deduplicated
so a human-facing list never depends on the order the model emitted picks.
A past deadline is flagged, not dropped -- a dead date on a live page is
exactly the kind of contradiction a human should see.

A pick whose day was invented (the page said "September 2026" and the
scanner stored 2026-09-01) is counted to the LAST day of that month, the
same rule liveness already applies. Without it a package contradicts the
liveness verdict on its own page: on 2026-09-15 the program is live and
the package says the deadline passed 14 days ago.
"""

from datetime import date

from granthound.seeds.profile import CommitmentWindow
from granthound.store.models import DeadlineMath, DeadlinePick
from granthound.tools.dates import end_of_month

WITHIN_DAYS = 14


def deadline_math(
    picks: list[DeadlinePick], today: date, windows: list[CommitmentWindow]
) -> list[DeadlineMath]:
    unique = {(p.iso, p.kind): p for p in picks}
    out: list[DeadlineMath] = []
    for (iso, kind), pick in sorted(unique.items(), key=lambda kv: (kv[0][0], kv[0][1].value)):
        deadline = date.fromisoformat(iso)
        # The date the counting runs to. It is the stored date, except when
        # the day was never printed -- then the page only promised "sometime
        # that month", and the last day of the month is the honest bound.
        # `iso` itself is left alone: it is what the scanner stored and what
        # every quote check and receipt is keyed on.
        counted_to = end_of_month(deadline) if pick.day_fabricated else deadline
        days = (counted_to - today).days
        # Window collision stays on the stored date: a window is a range the
        # org has already committed, and the stored date is the single day
        # the package names.
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
                day_fabricated=pick.day_fabricated,
            )
        )
    return out
