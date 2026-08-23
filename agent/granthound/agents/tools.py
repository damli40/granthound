"""Strands tool shims. Each is three lines: read the RunContext from
invocation_state and delegate to the pure stage function. Docstrings are
what the model sees, so they describe the parameters, not the code."""

from strands import tool
from strands.types.tools import ToolContext

from granthound.pipeline import stages


def _ctx(tool_context: ToolContext):
    return tool_context.invocation_state["ctx"]


@tool(context=True)
def fetch_and_snapshot(program_id: str, tool_context: ToolContext) -> str:
    """Fetch one program page, store a dated snapshot receipt, and return the deterministic summary.

    Args:
        program_id: one id from the task's program_ids list.
    """
    return stages.scout_fetch(_ctx(tool_context), program_id)


@tool(context=True)
def get_verification_brief(program_id: str, tool_context: ToolContext) -> str:
    """Get the flags, allowed dispositions, found dates, and fenced page text for one program.

    Args:
        program_id: one id from the task's program_ids list.
    """
    return stages.verifier_brief(_ctx(tool_context), program_id)


@tool(context=True)
def record_verification(
    program_id: str, disposition: str, reason: str, evidence_quotes: list[str], tool_context: ToolContext
) -> str:
    """Record the liveness decision for one program. Replies REJECTED with the exact problem if a value is not allowed.

    Args:
        program_id: one id from the task's program_ids list.
        disposition: one value from the brief's "allowed dispositions" list.
        reason: one value from the brief's "reason codes" list.
        evidence_quotes: 1 to 3 quotes copied verbatim from the page text, 8 to 400 characters each.
    """
    return stages.verifier_record(_ctx(tool_context), program_id, disposition, reason, evidence_quotes)


@tool(context=True)
def get_analysis_brief(program_id: str, tool_context: ToolContext) -> str:
    """Get the org profile, the verifier's finding, the scoring guide, and fenced page text for one live program.

    Args:
        program_id: one id from the task's program_ids list.
    """
    return stages.analyst_brief(_ctx(tool_context), program_id)


@tool(context=True)
def record_fit(
    program_id: str,
    eligibility: float,
    eligibility_quote: str,
    explicit_funding: float,
    explicit_funding_quote: str,
    effort_to_award: float,
    effort_to_award_quote: str,
    strategic: float,
    strategic_quote: str,
    reliability: float,
    reliability_quote: str,
    tool_context: ToolContext,
    headline_amount: float | None = None,
    reachable_amount: float | None = None,
    amount_quote: str | None = None,
) -> str:
    """Record the five fit-axis scores with a verbatim supporting quote each, and optional award amounts.

    Args:
        program_id: one id from the task's program_ids list.
        eligibility: 0 to 5; 0 means the org is structurally ineligible.
        eligibility_quote: verbatim page text supporting the eligibility score.
        explicit_funding: 0 to 5; does the page say it funds this kind of work for this kind of org.
        explicit_funding_quote: verbatim page text supporting the score.
        effort_to_award: 0 to 5; short application for a reachable award scores high.
        effort_to_award_quote: verbatim page text supporting the score.
        strategic: 0 to 5; a funder relationship worth having beyond this award scores high.
        strategic_quote: verbatim page text supporting the score.
        reliability: 0 to 5; clear dates, clear process, recent activity score high.
        reliability_quote: verbatim page text supporting the score.
        headline_amount: the largest per-award figure the page states; omit if the page states none.
        reachable_amount: the per-award figure the page states an applicant can receive; never above headline_amount.
        amount_quote: one verbatim page quote containing both figures; required when either amount is given.
    """
    return stages.analyst_record(
        _ctx(tool_context), program_id,
        eligibility, eligibility_quote, explicit_funding, explicit_funding_quote,
        effort_to_award, effort_to_award_quote, strategic, strategic_quote, reliability, reliability_quote,
        headline_amount=headline_amount, reachable_amount=reachable_amount, amount_quote=amount_quote,
    )


@tool(context=True)
def get_decision_brief(program_id: str, tool_context: ToolContext) -> str:
    """Get the dates you may pick, the deadline kinds, the org's commitment windows, and fenced page text for one program.

    Args:
        program_id: one id from the task's program_ids list.
    """
    return stages.clerk_brief(_ctx(tool_context), program_id)


@tool(context=True)
def record_decision_package(
    program_id: str,
    deadline_isos: list[str],
    deadline_kinds: list[str],
    requirement_quotes: list[str],
    eligibility_quotes: list[str],
    tool_context: ToolContext,
) -> str:
    """Record the decision package: picked deadlines (with kinds) and verbatim requirement and eligibility quotes.

    Args:
        program_id: one id from the task's program_ids list.
        deadline_isos: ISO dates chosen only from the brief's "dates you may pick" list.
        deadline_kinds: one kind per date, same order, from the brief's "deadline kinds" list.
        requirement_quotes: verbatim page text stating requirements (documents, forms, formats, budgets); at least one.
        eligibility_quotes: verbatim page text stating eligibility rules; at least one.
    """
    return stages.clerk_record(
        _ctx(tool_context), program_id, deadline_isos, deadline_kinds, requirement_quotes, eligibility_quotes
    )
