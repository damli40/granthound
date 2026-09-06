"""deadlines.ics: every future deadline the Clerk recorded, as an all-day event.

Pure over the export's program entries. Nothing here is composed by a
model: the date is the stored one, the label is a fixed name for the
stored kind, the description is the stored verdict, the stored collision
labels and the page URL. A month-only date is placed on the last day of
its month, which is the day the deadline math already counts to.
"""

import calendar as _cal
from datetime import date, datetime, timezone

KIND_LABEL = {
    "loi": "LOI", "full_application": "Full application", "info_session": "Info session",
    "award_notification": "Award notice", "cycle_opens": "Cycle opens", "other": "Date",
}


def _escape(text: str) -> str:
    return str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _event_date(iso: str, day_fabricated: bool) -> date:
    d = date.fromisoformat(iso)
    if not day_fabricated:
        return d
    return d.replace(day=_cal.monthrange(d.year, d.month)[1])


def _fold(line: str) -> str:
    """RFC 5545 folds lines longer than 75 octets; split on characters, good enough for ASCII-heavy text."""
    out, chunk = [], line
    while len(chunk.encode("utf-8")) > 75:
        out.append(chunk[:70])
        chunk = " " + chunk[70:]
    out.append(chunk)
    return "\r\n".join(out)


def build_ics(programs: list[dict], *, now: datetime) -> str:
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//GrantHound//deadlines//EN", "CALSCALE:GREGORIAN", "X-WR-CALNAME:GrantHound deadlines"]
    for p in sorted(programs, key=lambda x: x["program_id"]):
        package = p.get("decision_package") or {}
        for d in package.get("deadlines") or []:
            if d.get("is_past"):
                continue
            when = _event_date(d["iso"], bool(d.get("day_fabricated")))
            label = KIND_LABEL.get(d.get("kind"), "Date") + (" (month only)" if d.get("day_fabricated") else "")
            prefix = "[TEST FUNDER] " if p.get("is_fixture") else ""
            summary = f"{prefix}{p.get('funder') or p['program_id']}: {label}"
            parts = [f"Verdict {p.get('verdict') or 'not yet checked'}."]
            if d.get("collides_with"):
                parts.append("Collides with: " + ", ".join(d["collides_with"]) + ".")
            parts.append(p.get("url") or "")
            lines += [
                "BEGIN:VEVENT",
                f"UID:granthound-{p['program_id']}-{d['iso']}-{d.get('kind') or 'other'}@granthound",
                f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{when.strftime('%Y%m%d')}",
                f"SUMMARY:{_escape(summary)}",
                f"DESCRIPTION:{_escape(' '.join(parts))}",
                f"URL:{p.get('url') or ''}",
                "END:VEVENT",
            ]
    lines.append("END:VCALENDAR")
    return "".join(_fold(line) + "\r\n" for line in lines)
