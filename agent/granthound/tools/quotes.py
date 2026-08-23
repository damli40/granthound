"""Quote validation: the model may only quote text that is really on the page.

Comparison is whitespace-normalized (the normalizer already collapses runs,
but model output often re-wraps lines) and case-sensitive (a changed case
is a changed quote). Wrapping quotation marks the model adds around its
quote are stripped before checking; nothing else is forgiven.
"""

import re
from dataclasses import dataclass

_WS_RE = re.compile(r"\s+")
WRAPPING_QUOTES = "\"'“”‘’"


def normalize_ws(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


@dataclass(frozen=True)
class QuoteCheck:
    ok: list[str]
    bad: list[tuple[str, str]]

    @property
    def all_ok(self) -> bool:
        """True only when at least one quote was checked and every one passed.

        `bad` being empty is NOT the same question: it is also empty when the
        model quoted nothing at all. A model that cited nothing has proved
        nothing, so gate on this rather than on `not check.bad`.
        """
        return bool(self.ok) and not self.bad


def validate_quotes(
    quotes: list[str], norm_text: str, *, min_len: int = 8, max_len: int = 400
) -> QuoteCheck:
    haystack = normalize_ws(norm_text)
    ok: list[str] = []
    bad: list[tuple[str, str]] = []
    for raw in quotes:
        quote = normalize_ws(raw).strip(WRAPPING_QUOTES).strip()
        if len(quote) < min_len:
            bad.append((raw, f"shorter than {min_len} characters"))
        elif len(quote) > max_len:
            bad.append((raw, f"longer than {max_len} characters"))
        elif quote not in haystack:
            bad.append((raw, "not found verbatim in the page"))
        else:
            ok.append(quote)
    return QuoteCheck(ok=ok, bad=bad)


_CURRENCY_MARKER = r"(?:US\$|USD|\$)"


def _amount_forms(amount: float) -> list[tuple[str, str | None]]:
    """Every written form of `amount` we recognize, as (number, scale-suffix) pairs.

    The scale rules are divisibility rules, not rounding: 25000 is offered as
    "25K"/"25 thousand" because it is a whole number of thousands, while 25500
    is offered only as "25500" (it would have to be written $25.5K, which this
    deliberately does not recognize).
    """
    forms: list[tuple[str, str | None]] = [(str(int(amount)), None)]
    if amount >= 1000 and amount % 1000 == 0:
        thousands = str(int(amount // 1000))
        forms += [(thousands, "K"), (thousands, "k"), (thousands, "thousand")]
    if amount >= 1_000_000:
        millions = f"{amount / 1_000_000:g}"
        forms += [(millions, "M"), (millions, "m"), (millions, "million")]
    if amount >= 1_000_000_000:
        billions = f"{amount / 1_000_000_000:g}"
        forms += [(billions, "B"), (billions, "b"), (billions, "billion")]
    return forms


def amount_in_quote(amount: float, quote: str) -> bool:
    """True when the dollar figure appears in the quote as an actual dollar figure.

    A bare number on a funder page is far more often a year ("since 2000"),
    a day ("October 25, 2026") or a count ("50 grants") than an award, and
    amount_verified is a receipt value -- so a match only counts when it is
    anchored to a currency marker ($, US$, USD) immediately to its left.

    Accepted forms after that marker: plain digits (25000), comma-grouped
    (25,000), thousands as K or the word (25K / 25k / 25 thousand), millions
    as M or the word (1.5M / 1.5 million), billions as B or the word
    (1B / 1 billion). A digit or a letter immediately after the figure kills
    the match, so $25,000 never verifies 2500 and $25Kg never verifies 25000.

    The check is on the quote only; the quote itself must separately pass
    validate_quotes.
    """
    if amount <= 0:
        return False
    stripped = quote.replace(",", "")
    for number, suffix in _amount_forms(amount):
        figure = re.escape(number)
        if suffix is not None:
            figure += r"\s*" + re.escape(suffix)
        if re.search(rf"(?<![A-Za-z0-9]){_CURRENCY_MARKER}\s*{figure}(?![\dA-Za-z])", stripped):
            return True
    return False
