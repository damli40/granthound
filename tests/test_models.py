import pytest
from pydantic import ValidationError

from granthound.store.models import (
    Disposition,
    FitAxes,
    FoundDate,
    Verdict,
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
