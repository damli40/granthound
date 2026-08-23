"""TDD for granthound.tools.quotes -- proof that a quote the model returns is
really on the page.

Comparison is whitespace-normalized and case-sensitive; wrapping quotation
marks the model adds are stripped, and nothing else is forgiven. amount_in_quote
is the same idea for a dollar figure: the number must actually appear in the
sentence the model cited.
"""

from granthound.tools.quotes import amount_in_quote, normalize_ws, validate_quotes

PAGE = "Community Grants\n\nApplications are due   October 15, 2026.\nAwards range from $5,000 to $25,000 per organization."


def test_normalize_ws_collapses_runs_and_trims():
    assert normalize_ws("  a \n\n b\t c ") == "a b c"


def test_exact_quote_passes_even_across_whitespace_differences():
    check = validate_quotes(["Applications are due October 15, 2026."], PAGE)
    assert check.ok == ["Applications are due October 15, 2026."] and check.bad == []


def test_wrapping_quote_marks_are_stripped_before_checking():
    check = validate_quotes(['"Awards range from $5,000 to $25,000 per organization."'], PAGE)
    assert check.ok == ["Awards range from $5,000 to $25,000 per organization."]


def test_paraphrase_is_rejected_with_a_reason():
    check = validate_quotes(["Applications close October 15"], PAGE)
    assert check.ok == [] and check.bad == [("Applications close October 15", "not found verbatim in the page")]


def test_too_short_and_too_long_are_rejected():
    check = validate_quotes(["due", "x" * 401], PAGE, min_len=8, max_len=400)
    assert [reason for _, reason in check.bad] == ["shorter than 8 characters", "longer than 400 characters"]


def test_case_matters():
    assert validate_quotes(["applications are due October 15, 2026."], PAGE).ok == []


def test_amount_in_quote_accepts_plain_comma_and_k_forms():
    assert amount_in_quote(25000, "up to $25,000 per organization")
    assert amount_in_quote(25000, "up to $25000")
    assert amount_in_quote(25000, "grants of $25K")
    assert amount_in_quote(1500000, "a $1.5M fund")


def test_amount_in_quote_rejects_a_different_number():
    assert not amount_in_quote(25000, "up to $5,000 per organization")
    assert not amount_in_quote(2500, "up to $25,000 per organization")
