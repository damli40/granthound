"""The refinement lattice: what the Verifier may turn a deterministic suggestion into.

The deterministic layer (tools/dispositions.py) emits eight dispositions.
The LLM Verifier reads the page and may REFINE that suggestion -- e.g. turn
STALE_DATE_SUSPECT into VERIFIED_DEAD_PRIOR_YEAR once it has read "2025
applications are closed" -- but may never contradict a hard flag: nothing
the model says turns an all-dates-past page into VERIFIED_LIVE. Anything
outside the allowed set is overridden back to the suggestion and logged.

CHANGED_TERMS is deliberately absent: no deterministic gate exists for it
(only date-line changes are detected; a bare page diff fires on every nav
tweak and timestamp), so the Verifier cannot reach it in M2.
"""

from dataclasses import dataclass

from granthound.store.models import Disposition

D = Disposition

LIVE_FAMILY = frozenset(
    {D.ADDED, D.VERIFIED_LIVE, D.REVERIFIED_LIVE, D.CHANGED_DEADLINE, D.CHANGED_NEW_ROUND, D.WATCH_COMING_SOON}
)
DEAD_FAMILY = frozenset(
    {D.VERIFIED_DEAD_CLOSED, D.VERIFIED_DEAD_FINAL_CALL, D.VERIFIED_DEAD_PRIOR_YEAR, D.NO_PROGRAM_FOUND}
)
SUSPECT_FAMILY = frozenset({D.STALE_DATE_SUSPECT, D.YEAR_TRAP_SUSPECT, D.DATE_CONTRADICTION})

ALLOWED_REFINEMENTS: dict[Disposition, frozenset[Disposition]] = {
    D.ADDED: frozenset({D.VERIFIED_LIVE, D.WATCH_COMING_SOON}) | DEAD_FAMILY,
    D.VERIFIED_LIVE: frozenset({D.WATCH_COMING_SOON}) | DEAD_FAMILY,
    D.REVERIFIED_LIVE: frozenset({D.WATCH_COMING_SOON}) | DEAD_FAMILY,
    D.CHANGED_DEADLINE: frozenset({D.CHANGED_NEW_ROUND, D.WATCH_COMING_SOON}) | DEAD_FAMILY,
    D.STALE_DATE_SUSPECT: frozenset(
        {D.VERIFIED_DEAD_PRIOR_YEAR, D.VERIFIED_DEAD_CLOSED, D.VERIFIED_DEAD_FINAL_CALL, D.NO_PROGRAM_FOUND, D.WATCH_COMING_SOON}
    ),
    D.YEAR_TRAP_SUSPECT: frozenset({D.VERIFIED_DEAD_PRIOR_YEAR, D.NO_PROGRAM_FOUND, D.WATCH_COMING_SOON}),
    D.DATE_CONTRADICTION: frozenset({D.NO_PROGRAM_FOUND}),
    D.PAGE_UNREACHABLE: frozenset(),
}


@dataclass(frozen=True)
class RefinementResult:
    final: Disposition
    overridden: bool


def allowed_for(suggested: Disposition) -> frozenset[Disposition]:
    """The full set the Verifier may return for a suggestion (always includes the suggestion itself)."""
    return ALLOWED_REFINEMENTS.get(suggested, frozenset()) | {suggested}


def apply_refinement(suggested: Disposition, proposed: Disposition) -> RefinementResult:
    if proposed in allowed_for(suggested):
        return RefinementResult(final=proposed, overridden=False)
    return RefinementResult(final=suggested, overridden=True)
