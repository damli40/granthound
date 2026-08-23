"""TDD for granthound.tools.refinement -- the lattice that says which dispositions
the LLM Verifier may turn a deterministic suggestion into.

The tests below are the boundary rule in executable form: a hard deterministic
flag (every date past, a yearless date with nothing to vouch for it, two dates
that disagree, the page did not load) can never be talked up into a live
disposition, and CHANGED_TERMS is unreachable from anywhere in M2.
"""

import pytest

from granthound.store.models import Disposition
from granthound.tools.refinement import (
    ALLOWED_REFINEMENTS,
    DEAD_FAMILY,
    LIVE_FAMILY,
    SUSPECT_FAMILY,
    allowed_for,
    apply_refinement,
)

D = Disposition
DETERMINISTIC_OUTPUTS = {
    D.PAGE_UNREACHABLE, D.STALE_DATE_SUSPECT, D.YEAR_TRAP_SUSPECT, D.DATE_CONTRADICTION,
    D.ADDED, D.CHANGED_DEADLINE, D.VERIFIED_LIVE, D.REVERIFIED_LIVE,
}


def test_every_deterministic_output_has_a_lattice_entry():
    assert DETERMINISTIC_OUTPUTS <= set(ALLOWED_REFINEMENTS)


def test_changed_terms_is_unreachable_everywhere():
    for allowed in ALLOWED_REFINEMENTS.values():
        assert D.CHANGED_TERMS not in allowed


def test_hard_flags_can_never_be_refined_into_a_live_disposition():
    for suspect in SUSPECT_FAMILY | {D.PAGE_UNREACHABLE}:
        assert not (allowed_for(suspect) & {D.VERIFIED_LIVE, D.REVERIFIED_LIVE, D.ADDED, D.CHANGED_DEADLINE})


def test_families_are_disjoint_and_cover_every_verifier_outcome():
    assert not (LIVE_FAMILY & DEAD_FAMILY) and not (LIVE_FAMILY & SUSPECT_FAMILY) and not (DEAD_FAMILY & SUSPECT_FAMILY)
    reachable = set().union(*ALLOWED_REFINEMENTS.values()) | set(ALLOWED_REFINEMENTS)
    assert reachable <= LIVE_FAMILY | DEAD_FAMILY | SUSPECT_FAMILY | {D.PAGE_UNREACHABLE}


def test_allowed_refinement_is_taken():
    result = apply_refinement(D.ADDED, D.VERIFIED_DEAD_PRIOR_YEAR)
    assert result.final is D.VERIFIED_DEAD_PRIOR_YEAR and result.overridden is False


def test_disallowed_refinement_is_overridden_back_to_the_suggestion():
    result = apply_refinement(D.STALE_DATE_SUSPECT, D.VERIFIED_LIVE)
    assert result.final is D.STALE_DATE_SUSPECT and result.overridden is True


def test_repeating_the_suggestion_is_always_allowed():
    for suggested in DETERMINISTIC_OUTPUTS:
        result = apply_refinement(suggested, suggested)
        assert result.final is suggested and result.overridden is False


@pytest.mark.parametrize("suggested", [D.STALE_DATE_SUSPECT, D.YEAR_TRAP_SUSPECT])
def test_suspects_may_resolve_to_dead_or_coming_soon(suggested):
    assert {D.VERIFIED_DEAD_PRIOR_YEAR, D.WATCH_COMING_SOON} <= allowed_for(suggested)


def test_date_contradiction_can_only_stay_or_be_not_a_program():
    assert allowed_for(D.DATE_CONTRADICTION) == frozenset({D.DATE_CONTRADICTION, D.NO_PROGRAM_FOUND})
