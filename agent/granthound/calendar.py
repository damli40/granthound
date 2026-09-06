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
    """RFC 5545 folds lines longer than 75 octets, excluding the break.

    Cuts by UTF-8 octet, not by character: a character-count cut is wrong
    for anything outside ASCII (CJK, Arabic, ...), where a 70-character
    prefix can already be 200+ octets -- over the limit and never folded
    again, and a source string short enough in characters to be consumed
    whole leaves a continuation line that is nothing but the leading
    space. Every cut lands on a code-point boundary, never mid-character:
    it starts at a 70-octet prefix and backs off while the next byte is a
    UTF-8 continuation byte (10xxxxxx). 70 octets keeps ASCII output
    byte-identical to the previous character-based cut (an ASCII byte is
    never a continuation byte, so no backing off ever happens), while
    sitting well inside RFC 5545's 75-octet line limit for both the first
    line and every space-prefixed continuation line.
    """
    out, chunk = [], line
    while len(chunk.encode("utf-8")) > 75:
        data = chunk.encode("utf-8")
        cut = 70
        while cut > 0 and (data[cut] & 0xC0) == 0x80:
            cut -= 1
        out.append(data[:cut].decode("utf-8"))
        chunk = " " + data[cut:].decode("utf-8")
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
