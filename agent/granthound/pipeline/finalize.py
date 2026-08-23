"""Finalization: turns a RunContext into store rows. Runs after the graph,
always (the runner calls it in a finally block), so a crashed graph still
leaves one EVAL per program and one RUN item behind.

Order per program: derive verdict -> write EVAL (append-only) -> update META
pointers (guarded; a missing META is flagged, never created). The run item
is written last and its failure is NOT swallowed: a run that cannot be
logged must fail loudly, or the missing log reads as "no run happened".
"""

from collections import Counter
from dataclasses import dataclass
from datetime import timezone

from granthound.pipeline import stages
from granthound.pipeline.context import ProgramWork, RunContext
from granthound.store.models import Disposition, NodeUsage, Verdict
from granthound.tools.refinement import DEAD_FAMILY, LIVE_FAMILY


@dataclass
class ProgramOutcome:
    program_id: str
    verdict: Verdict
    disposition: Disposition
    eval_sk: str
    flags: list[str]


@dataclass
class RunSummary:
    run_id: str
    status: str
    outcomes: list[ProgramOutcome]
    run_item: dict
    errors: list[str]


def ensure_complete(ctx: RunContext) -> None:
    """Fill what the models skipped (deterministic fetch) and flag the rest."""
    for pid in ctx.program_ids:
        work = ctx.programs[pid]
        if work.det is None:
            try:
                stages.scout_fetch(ctx, pid, lazy=True)
            except Exception as exc:  # noqa: BLE001 -- one program's fetch error must not sink the batch
                work.flag("scout_error")
                work.error = f"{type(exc).__name__}: {exc}"
        det = work.det
        if det is None or det.snapshot_receipt is None:
            continue
        if work.verifier is None:
            work.flag("verifier_missing")
            continue
        if work.verifier.final in LIVE_FAMILY and work.fit is None:
            work.flag("analyst_missing")
            continue
        if pid in stages.needs_package(ctx) and work.package is None:
            work.flag("clerk_missing")


def derive_verdict(work: ProgramWork) -> tuple[Verdict, Disposition]:
    """The verdict for one program, from what is actually recorded.

    Every gate that fails answers NEEDS_HUMAN rather than guessing: a page
    nobody could fetch, a liveness call the lattice had to override, quotes
    that could not be found on the page, a missing record from any node.
    APPLY is reachable only when all four stages agree and every quote
    checked out.
    """
    det = work.det
    if det is None or det.snapshot_receipt is None:
        return Verdict.NEEDS_HUMAN, Disposition.PAGE_UNREACHABLE
    rec = work.verifier
    if rec is None:
        return Verdict.NEEDS_HUMAN, det.disposition
    liveness = rec.final
    # An overridden record is the model and the deterministic layer
    # disagreeing about whether the page is live. The stored final is the
    # deterministic suggestion, which for an override is either a suspect
    # disposition (NEEDS_HUMAN below anyway) or a live one -- and that live
    # case would otherwise walk through scoring to APPLY on a liveness call
    # the model got wrong. The disagreement itself goes to a human.
    if rec.overridden or rec.quotes_unverified:
        return Verdict.NEEDS_HUMAN, liveness
    if liveness in DEAD_FAMILY:
        return Verdict.PASS, liveness
    if liveness not in LIVE_FAMILY:
        # The suspect dispositions, and PAGE_UNREACHABLE, which belongs to no
        # family at all. Asking "is it suspect?" here would let anything
        # outside the three families fall through to scoring and reach APPLY;
        # asking "is it live?" scores only what a node called live.
        return Verdict.NEEDS_HUMAN, liveness
    fit = work.fit
    if fit is None or fit.quotes_unverified:
        return Verdict.NEEDS_HUMAN, liveness
    if fit.fit.capped:
        return Verdict.PASS, Disposition.SKIPPED_ELIGIBILITY
    suggestion = fit.fit.verdict_suggestion
    if suggestion is Verdict.PASS:
        return Verdict.PASS, Disposition.SKIPPED_FIT_LOW_SCORE
    if suggestion is Verdict.WATCH:
        return Verdict.WATCH, liveness
    package = work.package
    if package is None or package.quotes_unverified:
        return Verdict.NEEDS_HUMAN, liveness
    return Verdict.APPLY, liveness


def assemble_eval_item(work: ProgramWork, verdict: Verdict, disposition: Disposition, pipeline_status: str) -> dict:
    if work.det is not None:
        base = work.det.model_dump(mode="json")
    else:
        base = {
            "program_id": work.program_id, "url": work.url, "snapshot_receipt": None,
            "date_scan": None, "diff_receipt": None, "disposition": None,
        }
    deterministic = base.pop("disposition")
    return {
        **base,
        "stage": "final",
        "pipeline_status": pipeline_status,
        "deterministic_disposition": deterministic,
        "liveness_disposition": work.verifier.final.value if work.verifier else None,
        "disposition": disposition.value,
        "verdict": verdict.value,
        "verifier": work.verifier.model_dump(mode="json") if work.verifier else None,
        "fit": work.fit.model_dump(mode="json") if work.fit else None,
        "decision_package": work.package.model_dump(mode="json") if work.package else None,
        "flags": sorted(set(work.flags)),
        "error": work.error,
    }


def finalize_run(
    ctx: RunContext, *, node_usage: dict[str, NodeUsage], pipeline_status: str, error: str | None
) -> RunSummary:
    ensure_complete(ctx)
    outcomes: list[ProgramOutcome] = []
    errors: list[str] = []
    for pid in ctx.program_ids:
        work = ctx.programs[pid]
        verdict, disposition = derive_verdict(work)
        item = assemble_eval_item(work, verdict, disposition, pipeline_status)
        try:
            sk = ctx.store.put_evaluation(pid, ctx.run_id, item, at=ctx.at)
        except Exception as exc:  # noqa: BLE001 -- keep writing the other programs; report at the end
            errors.append(f"{pid}: put_evaluation failed: {type(exc).__name__}: {exc}")
            continue
        sha = work.det.snapshot_receipt.sha256 if work.det and work.det.snapshot_receipt else ""
        fit_score = work.fit.fit.score if work.fit else None
        try:
            pointed = ctx.store.update_meta_pointers(
                pid, verdict=verdict.value, fit_score=fit_score, latest_eval_sk=sk, latest_snapshot_sha=sha
            )
        except Exception as exc:  # noqa: BLE001 -- same reason as the EVAL write: one program must not sink the rest
            # The EVAL is already written, so the run is not lost -- only the
            # META pointer to it is stale. Letting this propagate would cost
            # every program after this one its EVAL row AND the run log.
            errors.append(f"{pid}: update_meta_pointers failed: {type(exc).__name__}: {exc}")
            work.flag("meta_pointer_failed")
        else:
            if not pointed:
                work.flag("meta_missing")
        outcomes.append(ProgramOutcome(pid, verdict, disposition, sk, sorted(set(work.flags))))

    status = "partial" if errors else pipeline_status
    run_item = {
        "run_id": ctx.run_id,
        "at": ctx.at.astimezone(timezone.utc).isoformat(),
        "status": status,
        "error": error,
        "errors": errors,
        "program_ids": ctx.program_ids,
        "node_models": dict(ctx.node_models),
        "node_usage": {node: usage.model_dump() for node, usage in node_usage.items()},
        "verdict_counts": dict(Counter(o.verdict.value for o in outcomes)),
        "disposition_counts": dict(Counter(o.disposition.value for o in outcomes)),
        "flag_counts": dict(Counter(flag for o in outcomes for flag in o.flags)),
        "overrides": sum(1 for w in ctx.programs.values() if w.verifier is not None and w.verifier.overridden),
    }
    ctx.store.put_run(run_item)
    return RunSummary(run_id=ctx.run_id, status=status, outcomes=outcomes, run_item=run_item, errors=errors)
