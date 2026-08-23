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


def amount_in_quote(amount: float, quote: str) -> bool:
    """True when the dollar figure appears in the quote in a recognizable form.

    Accepted forms: plain digits (25000), comma-grouped (25,000), thousands
    with K (25K / 25k), millions with M (1.5M). The check is on the quote
    only; the quote itself must separately pass validate_quotes.
    """
    if amount <= 0:
        return False
    stripped = quote.replace(",", "")
    forms = {str(int(amount))}
    if amount >= 1000 and amount % 1000 == 0:
        forms.add(f"{int(amount // 1000)}K")
        forms.add(f"{int(amount // 1000)}k")
    if amount >= 1_000_000:
        forms.add(f"{amount / 1_000_000:g}M")
        forms.add(f"{amount / 1_000_000:g}m")
    return any(re.search(rf"(?<![\d.]){re.escape(form)}(?![\d])", stripped) for form in forms)
