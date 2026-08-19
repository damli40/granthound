import re
from datetime import date, datetime

from dateutil import parser as dateparser

from granthound.store.models import DateScan, FoundDate

MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December|"
    "Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)

DATE_CANDIDATE_RE = re.compile(
    rf"(?:(?:{MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?)"
    rf"|(?:\d{{1,2}}\s+(?:{MONTHS})\.?(?:,?\s+\d{{4}})?)"
    r"|(?:\d{4}-\d{2}-\d{2})"
    r"|(?:\d{1,2}/\d{1,2}/\d{4})",
    re.IGNORECASE,
)

DEADLINE_WORDS = frozenset(
    ["deadline", "due", "close", "closes", "closing", "apply by", "submit by", "submission"]
)

_DEFAULT_A = datetime(2001, 1, 1)
_DEFAULT_B = datetime(2002, 2, 2)
_CONTEXT_CHARS = 120
_CONTRADICTION_GAP_DAYS = 30


def _parse_candidate(raw: str) -> tuple[str | None, bool] | None:
    """Return (iso_date_or_None, year_present) or None on parse failure.

    Tri-state return:
    - None: parse failed (ValueError/OverflowError) — skip this candidate
    - (None, False): yearless date (two defaults disagree on year) — append as yearless
    - (iso_str, True): year present — append with iso
    """
    try:
        a = dateparser.parse(raw, default=_DEFAULT_A)
        b = dateparser.parse(raw, default=_DEFAULT_B)
    except (ValueError, OverflowError):
        return None
    if a.year != b.year:
        return None, False
    return a.date().isoformat(), True


def _is_deadline_context(context: str) -> bool:
    lowered = context.lower()
    return any(word in lowered for word in DEADLINE_WORDS)


def extract_dates(text: str, today: date) -> DateScan:
    found: list[FoundDate] = []
    for match in DATE_CANDIDATE_RE.finditer(text):
        raw = match.group(0)
        start = max(0, match.start() - _CONTEXT_CHARS)
        context = text[start : match.end() + _CONTEXT_CHARS]
        result = _parse_candidate(raw)
        if result is None:
            continue
        iso, year_present = result
        found.append(FoundDate(raw=raw, iso=iso, year_present=year_present, context=context))

    dated = [d for d in found if d.year_present and d.iso is not None]
    all_past = bool(dated) and all(date.fromisoformat(d.iso) < today for d in dated)
    has_yearless = any(not d.year_present for d in found)

    future_deadlines = sorted(
        date.fromisoformat(d.iso)
        for d in dated
        if date.fromisoformat(d.iso) >= today and _is_deadline_context(d.context)
    )
    contradict = (
        len(future_deadlines) >= 2
        and (future_deadlines[-1] - future_deadlines[0]).days > _CONTRADICTION_GAP_DAYS
    )

    return DateScan(
        dates=found,
        all_dates_past=all_past,
        has_yearless_date=has_yearless,
        dates_contradict=contradict,
    )
