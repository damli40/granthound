import pytest
from pydantic import ValidationError

from granthound.store.models import (
    DeadlineKind,
    DeadlineMath,
    DecisionPackage,
    Disposition,
    FitAxes,
    FitRecord,
    FitScore,
    FoundDate,
    ReasonCode,
    Verdict,
    VerifierRecord,
)


def test_disposition_has_exactly_20_closed_values():
    assert len(Disposition) == 20
    assert Disposition.VERIFIED_DEAD_PRIOR_YEAR.value == "verified_dead_prior_year"
    assert Disposition.YEAR_TRAP_SUSPECT.value == "year_trap_suspect"


def test_verdict_members():
    assert {v.value for v in Verdict} == {"APPLY", "PASS", "WATCH", "NEEDS_HUMAN"}


def test_fit_axes_rejects_out_of_range():
    with pytest.raises(ValidationError):
        FitAxes(eligibility=6, explicit_funding=0, effort_to_award=0, strategic=0, reliability=0)


def test_found_date_yearless_has_no_iso():
    d = FoundDate(raw="March 15", iso=None, year_present=False, context="due March 15")
    assert d.iso is None and d.year_present is False


def test_quotes_unverified_is_required_on_every_record_that_carries_quotes():
    """The flag means "these quotes were NOT checked against the snapshot".

    A default of False would make every construction path that forgets it
    claim the quotes WERE checked -- a provenance lie that no test would
    catch. So there is no default: the author has to state it, exactly as
    amount_verified already forces the author to state it.

    Each model is first constructed successfully WITH the flag, so the
    ValidationError below can only be about the missing flag and not about
    some other field being wrong.
    """
    verifier = dict(
        proposed=Disposition.ADDED,
        final=Disposition.VERIFIED_LIVE,
        overridden=False,
        reason=ReasonCode.DEADLINE_IN_FUTURE,
        evidence_quotes=["Applications are due October 15, 2026."],
    )
    fit = dict(
        axes=FitAxes(eligibility=5, explicit_funding=4, effort_to_award=3, strategic=4, reliability=5),
        axis_quotes={"eligibility": "open to 501(c)(3) organizations"},
        fit=FitScore(score=4.1, capped=False, verdict_suggestion=Verdict.APPLY),
        headline_amount=25000.0,
        reachable_amount=25000.0,
        amount_quote="up to $25,000",
        amount_verified=True,
    )
    package = dict(
        deadlines=[
            DeadlineMath(
                iso="2026-10-15",
                kind=DeadlineKind.FULL_APPLICATION,
                days_until=53,
                within_14_days=False,
                is_past=False,
                collides_with=[],
            )
        ],
        requirement_quotes=[],
        eligibility_quotes=[],
    )

    assert VerifierRecord(**verifier, quotes_unverified=False).quotes_unverified is False
    assert FitRecord(**fit, quotes_unverified=True).quotes_unverified is True
    assert DecisionPackage(**package, quotes_unverified=False).quotes_unverified is False

    for model, kwargs in ((VerifierRecord, verifier), (FitRecord, fit), (DecisionPackage, package)):
        with pytest.raises(ValidationError):
            model(**kwargs)
