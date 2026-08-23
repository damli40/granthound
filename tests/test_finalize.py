from datetime import datetime, timezone

import pytest

from granthound.pipeline import stages
from granthound.pipeline.context import RunContext
from granthound.pipeline.finalize import assemble_eval_item, derive_verdict, ensure_complete, finalize_run
from granthound.store.models import (
    DecisionPackage,
    Disposition,
    FitAxes,
    FitRecord,
    NodeUsage,
    ReasonCode,
    Verdict,
    VerifierRecord,
)
from granthound.tools.scoring import compute_fit_score
from tests.fakes import DEAD_URL, DOWN_URL, LIVE_URL, ORG, PAGES, MemoryStore, make_fetcher, seeded_store

AT = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def make_ctx(store=None, ids=("p-live", "p-dead", "p-down")):
    store = store or seeded_store()
    urls = {"p-live": LIVE_URL, "p-dead": DEAD_URL, "p-down": DOWN_URL}
    return RunContext.create([(pid, urls[pid]) for pid in ids], AT, store=store, fetcher=make_fetcher(PAGES), org=ORG)


def verifier(final, *, proposed=None, unverified=False):
    return VerifierRecord(
        proposed=proposed or final, final=final, overridden=(proposed is not None and proposed != final),
        reason=ReasonCode.DEADLINE_IN_FUTURE, evidence_quotes=["q"], quotes_unverified=unverified,
    )


def fit(eligibility=5.0, other=4.0, *, unverified=False):
    axes = FitAxes(eligibility=eligibility, explicit_funding=other, effort_to_award=other, strategic=other, reliability=other)
    return FitRecord(axes=axes, axis_quotes={}, fit=compute_fit_score(axes), headline_amount=None, reachable_amount=None,
                     amount_quote=None, amount_verified=False, quotes_unverified=unverified)


def package(unverified=False):
    return DecisionPackage(deadlines=[], requirement_quotes=[], eligibility_quotes=[], quotes_unverified=unverified)


def test_unreachable_is_needs_human():
    ctx = make_ctx()
    stages.scout_fetch(ctx, "p-down")
    assert derive_verdict(ctx.work("p-down")) == (Verdict.NEEDS_HUMAN, Disposition.PAGE_UNREACHABLE)


def test_verdict_matrix():
    ctx = make_ctx()
    stages.scout_fetch(ctx, "p-live")
    work = ctx.work("p-live")
    assert derive_verdict(work) == (Verdict.NEEDS_HUMAN, Disposition.ADDED)
    work.verifier = verifier(Disposition.VERIFIED_DEAD_PRIOR_YEAR)
    assert derive_verdict(work) == (Verdict.PASS, Disposition.VERIFIED_DEAD_PRIOR_YEAR)
    work.verifier = verifier(Disposition.STALE_DATE_SUSPECT, proposed=Disposition.VERIFIED_LIVE)
    assert derive_verdict(work) == (Verdict.NEEDS_HUMAN, Disposition.STALE_DATE_SUSPECT)
    work.verifier = verifier(Disposition.VERIFIED_LIVE, unverified=True)
    assert derive_verdict(work) == (Verdict.NEEDS_HUMAN, Disposition.VERIFIED_LIVE)
    work.verifier = verifier(Disposition.VERIFIED_LIVE)
    assert derive_verdict(work) == (Verdict.NEEDS_HUMAN, Disposition.VERIFIED_LIVE)
    work.fit = fit(eligibility=0.0)
    assert derive_verdict(work) == (Verdict.PASS, Disposition.SKIPPED_ELIGIBILITY)
    work.fit = fit(eligibility=2.0, other=2.0)
    assert derive_verdict(work) == (Verdict.PASS, Disposition.SKIPPED_FIT_LOW_SCORE)
    work.fit = fit(eligibility=3.0, other=3.0)
    assert derive_verdict(work) == (Verdict.WATCH, Disposition.VERIFIED_LIVE)
    work.fit = fit()
    assert derive_verdict(work) == (Verdict.NEEDS_HUMAN, Disposition.VERIFIED_LIVE)
    work.package = package(unverified=True)
    assert derive_verdict(work) == (Verdict.NEEDS_HUMAN, Disposition.VERIFIED_LIVE)
    work.package = package()
    assert derive_verdict(work) == (Verdict.APPLY, Disposition.VERIFIED_LIVE)
    work.fit = fit(unverified=True)
    assert derive_verdict(work) == (Verdict.NEEDS_HUMAN, Disposition.VERIFIED_LIVE)


def test_an_overridden_liveness_record_never_reaches_apply():
    """A record the lattice had to override is a disagreement, not a decision.

    The stored final is the deterministic suggestion, which for an override
    is always either a suspect disposition or a live one -- and the live
    case would otherwise walk straight through scoring to APPLY on a
    liveness call the model got wrong. It goes to a human instead.
    """
    ctx = make_ctx()
    stages.scout_fetch(ctx, "p-live")
    work = ctx.work("p-live")
    work.verifier = verifier(Disposition.ADDED, proposed=Disposition.CHANGED_DEADLINE)
    work.fit = fit()
    work.package = package()
    assert work.verifier.overridden is True
    assert derive_verdict(work) == (Verdict.NEEDS_HUMAN, Disposition.ADDED)


def test_a_liveness_disposition_in_no_family_is_never_scored():
    """page_unreachable belongs to no refinement family.

    A dispatch written as "dead -> PASS, suspect -> NEEDS_HUMAN, otherwise
    score it" would send this straight through scoring to APPLY, on a page
    the record itself says nobody could read. Only a live disposition is
    scored.
    """
    ctx = make_ctx()
    stages.scout_fetch(ctx, "p-live")
    work = ctx.work("p-live")
    work.verifier = verifier(Disposition.PAGE_UNREACHABLE)
    work.fit = fit()
    work.package = package()
    assert derive_verdict(work) == (Verdict.NEEDS_HUMAN, Disposition.PAGE_UNREACHABLE)


def test_assemble_eval_item_shape():
    ctx = make_ctx()
    stages.scout_fetch(ctx, "p-live")
    work = ctx.work("p-live")
    work.verifier = verifier(Disposition.VERIFIED_LIVE)
    work.fit = fit(eligibility=0.0)
    item = assemble_eval_item(work, Verdict.PASS, Disposition.SKIPPED_ELIGIBILITY, "ok")
    assert item["stage"] == "final" and item["pipeline_status"] == "ok"
    assert item["deterministic_disposition"] == "added"
    assert item["liveness_disposition"] == "verified_live"
    assert item["disposition"] == "skipped_eligibility" and item["verdict"] == "PASS"
    assert item["snapshot_receipt"]["sha256"] == work.det.snapshot_receipt.sha256
    assert item["fit"]["fit"]["capped"] is True and item["decision_package"] is None
    assert "norm_text" not in item and item["flags"] == []


def test_ensure_complete_fills_and_flags():
    ctx = make_ctx()
    stages.scout_fetch(ctx, "p-live")
    ctx.work("p-live").verifier = verifier(Disposition.VERIFIED_LIVE)
    ensure_complete(ctx)
    assert ctx.work("p-dead").det is not None and "scout_missed" in ctx.work("p-dead").flags
    assert "verifier_missing" in ctx.work("p-dead").flags
    assert "analyst_missing" in ctx.work("p-live").flags
    assert ctx.work("p-down").flags == ["scout_missed"]


def test_finalize_writes_one_eval_per_program_pointers_and_a_run_item():
    ctx = make_ctx()
    stages.scout_fetch(ctx, "p-live")
    ctx.work("p-live").verifier = verifier(Disposition.VERIFIED_LIVE)
    ctx.work("p-live").fit = fit()
    ctx.work("p-live").package = package()
    usage = {"scout": NodeUsage(model_id="m", input_tokens=1, output_tokens=2, total_tokens=3, execution_ms=4)}
    summary = finalize_run(ctx, node_usage=usage, pipeline_status="ok", error=None)
    assert summary.status == "ok" and summary.errors == []
    assert {o.program_id: o.verdict for o in summary.outcomes} == {
        "p-live": Verdict.APPLY, "p-dead": Verdict.NEEDS_HUMAN, "p-down": Verdict.NEEDS_HUMAN,
    }
    for pid in ("p-live", "p-dead", "p-down"):
        assert len(ctx.store.evals[pid]) == 1
        assert ctx.store.get_last_eval(pid)["stage"] == "final"
    assert ctx.store.meta["p-live"]["verdict"] == "APPLY" and ctx.store.meta["p-live"]["fit_score"] == 4.3
    run = ctx.store.runs[ctx.run_id]
    assert run["program_ids"] == ["p-dead", "p-down", "p-live"]
    assert run["node_usage"]["scout"]["total_tokens"] == 3
    assert run["verdict_counts"] == {"APPLY": 1, "NEEDS_HUMAN": 2}
    assert run["flag_counts"]["verifier_missing"] == 1 and run["flag_counts"]["scout_missed"] == 2


def test_unseeded_program_is_flagged_meta_missing_not_ghost_created():
    ctx = make_ctx(store=MemoryStore(), ids=("p-live",))
    stages.scout_fetch(ctx, "p-live")
    summary = finalize_run(ctx, node_usage={}, pipeline_status="ok", error=None)
    assert "meta_missing" in summary.outcomes[0].flags
    assert ctx.store.meta == {}


def test_a_fetch_that_explodes_is_recorded_not_lost():
    """The one path that sets ProgramWork.error: nothing in stages does.

    evaluate_program only swallows requests' own transport errors, so any
    other failure comes back out of the lazy fetch inside ensure_complete.
    The program still gets its EVAL row, with the exception named in it.
    """

    def angry_fetcher(url):
        raise ValueError("dns exploded")

    store = seeded_store()
    ctx = RunContext.create([("p-live", LIVE_URL)], AT, store=store, fetcher=angry_fetcher, org=ORG)
    summary = finalize_run(ctx, node_usage={}, pipeline_status="ok", error=None)
    outcome = summary.outcomes[0]
    assert outcome.verdict is Verdict.NEEDS_HUMAN and outcome.disposition is Disposition.PAGE_UNREACHABLE
    assert "scout_error" in outcome.flags
    item = store.get_last_eval("p-live")
    assert "ValueError" in item["error"] and item["snapshot_receipt"] is None
    assert item["stage"] == "final" and item["url"] == LIVE_URL


def test_a_pointer_write_failure_costs_no_other_program_its_eval():
    ctx = make_ctx()
    real = ctx.store.update_meta_pointers

    def flaky(program_id, **kwargs):
        if program_id == "p-dead":
            raise RuntimeError("ddb throttled")
        return real(program_id, **kwargs)

    ctx.store.update_meta_pointers = flaky
    summary = finalize_run(ctx, node_usage={}, pipeline_status="ok", error=None)
    assert summary.status == "partial"
    assert any("p-dead" in message and "ddb throttled" in message for message in summary.errors)
    assert all(len(ctx.store.evals[pid]) == 1 for pid in ("p-live", "p-dead", "p-down"))
    assert ctx.store.meta["p-live"]["verdict"] == "NEEDS_HUMAN"
    assert ctx.run_id in ctx.store.runs


def test_run_log_failure_is_not_swallowed():
    ctx = make_ctx()

    def boom(item):
        raise RuntimeError("ddb down")

    ctx.store.put_run = boom
    with pytest.raises(RuntimeError, match="ddb down"):
        finalize_run(ctx, node_usage={}, pipeline_status="ok", error=None)
    assert all(len(ctx.store.evals[pid]) == 1 for pid in ("p-live", "p-dead", "p-down"))
