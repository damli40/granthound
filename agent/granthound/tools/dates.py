import calendar
import re
from datetime import date, datetime

from dateutil import parser as dateparser

from granthound.store.models import DateScan, FoundDate

MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December|"
    "Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
)

# Month tokens require a real capitalized month word: \b anchors the start
# so a match can't begin mid-word (blocks "Weimar" -> "mar"), and the
# trailing (?![A-Za-z]) blocks a letter continuation (blocks "20 Marion" ->
# "20 Mar"). The pattern is intentionally NOT case-insensitive: grant/funder
# prose capitalizes real month mentions ("May 1, 2026", "May 2026") but
# common lowercase words that happen to spell a month abbreviation
# ("grantees may 20 percent") do not -- case is the only signal available
# to tell "May the month" from "may the modal verb" apart, since both are
# already properly word-bounded on their own.
DATE_CANDIDATE_RE = re.compile(
    rf"(?:\b(?:{MONTHS})(?![A-Za-z])\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?!\d)(?:,?\s+\d{{4}})?)"
    rf"|(?:\d{{1,2}}\s+\b(?:{MONTHS})(?![A-Za-z])\.?(?:,?\s+\d{{4}})?)"
    rf"|(?:\b(?:{MONTHS})(?![A-Za-z])\.?,?\s+\d{{4}}(?!\d))"
    r"|(?:\d{4}-\d{2}-\d{2})"
    r"|(?:\d{1,2}/\d{1,2}/\d{4})"
)

DEADLINE_WORDS = frozenset(
    ["deadline", "due", "close", "closes", "closing", "apply by", "submit by", "submission"]
)

# Word-boundary versions of DEADLINE_WORDS -- a plain substring check
# false-positives inside an unrelated word (e.g. "close" inside
# "enclosed"). Multi-word entries ("apply by") keep their internal space;
# \b only anchors the two ends.
_DEADLINE_WORD_RES = [re.compile(rf"\b{re.escape(word)}\b") for word in DEADLINE_WORDS]

_DEFAULT_A = datetime(2001, 1, 1)
_DEFAULT_B = datetime(2002, 2, 2)
_CONTEXT_CHARS = 120
_CONTRADICTION_GAP_DAYS = 30


def _parse_candidate(raw: str) -> tuple[str | None, bool, bool] | None:
    """Return (iso_date_or_None, year_present, day_fabricated) or None on parse failure.

    Tri-state return:
    - None: parse failed (ValueError/OverflowError) — skip this candidate
    - (None, False, False): yearless date (two defaults disagree on year) — append as yearless
    - (iso_str, True, day_fabricated): year present — append with iso

    `_DEFAULT_A`/`_DEFAULT_B` disagree on both year (2001 vs 2002) and day
    (1 vs 2). A raw candidate that omits its year parses to a different
    year under each default (caught above); a raw candidate that gives a
    year but omits its day (e.g. "August 2026") parses to the SAME year
    but a DIFFERENT day under each default -- that is the day_fabricated
    signal, and it means `iso`'s day digit is not real information from
    the page.
    """
    try:
        a = dateparser.parse(raw, default=_DEFAULT_A)
        b = dateparser.parse(raw, default=_DEFAULT_B)
    except (ValueError, OverflowError):
        return None
    if a.year != b.year:
        return None, False, False
    day_fabricated = a.day != b.day
    return a.date().isoformat(), True, day_fabricated


def _is_deadline_context(context: str) -> bool:
    lowered = context.lower()
    return any(pattern.search(lowered) for pattern in _DEADLINE_WORD_RES)


def _end_of_month(d: date) -> date:
    last_day = calendar.monthrange(d.year, d.month)[1]
    return d.replace(day=last_day)


def extract_dates(text: str, today: date) -> DateScan:
    found: list[FoundDate] = []
    for match in DATE_CANDIDATE_RE.finditer(text):
        raw = match.group(0)
        start = max(0, match.start() - _CONTEXT_CHARS)
        context = text[start : match.end() + _CONTEXT_CHARS]
        result = _parse_candidate(raw)
        if result is None:
            continue
        iso, year_present, day_fabricated = result
        found.append(
            FoundDate(
                raw=raw,
                iso=iso,
                year_present=year_present,
                context=context,
                day_fabricated=day_fabricated,
            )
        )

    dated = [d for d in found if d.year_present and d.iso is not None]

    def _all_past_comparison_date(d: FoundDate) -> date:
        parsed = date.fromisoformat(d.iso)
        # A fabricated day (e.g. "August 2026" -> day=1) understates how
        # long the date might still be current: the page only promised
        # "sometime in August", not August 1st specifically, so treat it
        # as still live through the LAST day of that month rather than
        # the fabricated first day.
        return _end_of_month(parsed) if d.day_fabricated else parsed

    all_past = bool(dated) and all(_all_past_comparison_date(d) < today for d in dated)
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
